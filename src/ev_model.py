from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from src.rng import ComponentSelection, ComponentStream


EXPECTED_FULL_YEAR_STEPS = 35_040
STEP_HOURS = 0.25
LOCAL_TIMEZONE = "Europe/Amsterdam"
ADOPTION_SCHEMA_VERSION = 1
EV_HOME_COMPONENT = "ev_home"
EV_PUBLIC_COMPONENT = "ev_public"
EV_INTEGRATION_READINESS_SCHEMA_VERSION = 1
EV_CALENDAR_MAPPING_RULE_ID = "EV-CAL-001"
EV_CALENDAR_MAPPING_RULE_VERSION = "ordinal-v1"
EV_SOURCE_CALENDAR_ID = "elaad-2025-europe-amsterdam-15min"
EV_TARGET_CALENDAR_ID = "planning-2035-europe-amsterdam-15min"
EV_PUBLIC_SET_B_LIBRARY_ID = "B_public_vancar_cp_y2030_equal_mix"
EV_PUBLIC_SET_B_CAPACITY_MIX = (
    ("public_11kw", 11, 0.25),
    ("public_13kw", 13, 0.25),
    ("public_15kw", 15, 0.25),
    ("public_22kw", 22, 0.25),
)


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



@dataclass(frozen=True)
class EVMappedProfileBatch:
    """EV profile batch after approved EV-CAL-001 ordinal calendar mapping."""

    member_ids: tuple[str, ...]
    source_datetimes_utc: tuple[datetime, ...]
    source_datetimes_local: tuple[datetime, ...]
    target_datetimes_utc: tuple[datetime, ...]
    target_datetimes_local: tuple[datetime, ...]
    demands_kw: np.ndarray
    batch_seed: int
    mapping_provenance: dict[str, object]

    @property
    def n_timesteps(self) -> int:
        return int(self.demands_kw.shape[0])

    @property
    def n_profiles(self) -> int:
        return int(self.demands_kw.shape[1])
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



def canonical_ev_planning_calendar_2035() -> tuple[tuple[datetime, ...], tuple[datetime, ...]]:
    """Return the signed 2035 IC-1 EV target calendar for EV-CAL-001."""

    first_local = datetime(2035, 1, 1, 0, 0, tzinfo=_local_zone())
    first_utc = first_local.astimezone(UTC)
    datetimes_utc = tuple(
        first_utc + timedelta(minutes=15 * index) for index in range(EXPECTED_FULL_YEAR_STEPS)
    )
    datetimes_local = tuple(item.astimezone(_local_zone()) for item in datetimes_utc)
    _validate_utc_time_axis(datetimes_utc, EXPECTED_FULL_YEAR_STEPS, label="2035 EV target calendar")
    return datetimes_utc, datetimes_local


def apply_ev_cal001_ordinal_mapping(
    batch: ElaadProfileBatch,
    *,
    component_id: str,
    library_id: str,
    processed_path: str,
    processed_sha256_file: str,
    partition: str = "candidate",
    target_datetimes_utc: Sequence[datetime] | None = None,
    target_datetimes_local: Sequence[datetime] | None = None,
) -> EVMappedProfileBatch:
    """Map complete EV source profiles to 2035 by signed ordinal timestep index."""

    if partition != "candidate":
        raise ValueError("EV-CAL-001 readiness mapping accepts candidate batches only")
    if component_id not in {EV_HOME_COMPONENT, EV_PUBLIC_COMPONENT}:
        raise ValueError("EV-CAL-001 mapping requires a supported EV component_id")
    _require_non_empty_string(library_id, "library_id")
    _require_non_empty_string(processed_path, "processed_path")
    _require_sha256(processed_sha256_file, "processed_sha256_file")
    if batch.n_timesteps != EXPECTED_FULL_YEAR_STEPS:
        raise ValueError("EV-CAL-001 requires complete 35,040-step source profiles")
    if len(batch.member_ids) != batch.n_profiles:
        raise ValueError("EV-CAL-001 requires one member ID per source profile")
    _validate_utc_time_axis(batch.datetimes_utc, EXPECTED_FULL_YEAR_STEPS, label="EV source calendar")

    if target_datetimes_utc is None or target_datetimes_local is None:
        target_utc, target_local = canonical_ev_planning_calendar_2035()
    else:
        target_utc = tuple(target_datetimes_utc)
        target_local = tuple(target_datetimes_local)
    _validate_utc_time_axis(target_utc, EXPECTED_FULL_YEAR_STEPS, label="2035 EV target calendar")
    if len(target_local) != EXPECTED_FULL_YEAR_STEPS:
        raise ValueError("2035 EV target local calendar must have 35,040 timestamps")

    provenance = {
        "calendar_mapping_rule_id": EV_CALENDAR_MAPPING_RULE_ID,
        "calendar_mapping_rule_version": EV_CALENDAR_MAPPING_RULE_VERSION,
        "mapping_option": "ordinal_timestep_mapping",
        "source_calendar_id": EV_SOURCE_CALENDAR_ID,
        "target_calendar_id": EV_TARGET_CALENDAR_ID,
        "source_timestamp_index_policy": "target_index_i_uses_source_index_i",
        "source_timestep_count": EXPECTED_FULL_YEAR_STEPS,
        "target_timestep_count": EXPECTED_FULL_YEAR_STEPS,
        "unmapped_or_repeated_source_timestep_count": 0,
        "weekday_weekend_preserved": False,
        "season_order_preserved": True,
        "serial_order_preserved": True,
        "annual_energy_preserved": True,
        "dst_policy": "target calendar is a contiguous UTC 15-minute axis converted to Europe/Amsterdam local time",
        "holiday_policy": "no holiday remapping in ordinal EV-CAL-001",
        "component_id": component_id,
        "library_id": library_id,
        "batch_seed": batch.batch_seed,
        "member_id_policy": "member IDs are preserved from source batch",
        "candidate_processed_path": processed_path,
        "candidate_processed_sha256_file": processed_sha256_file,
        "partition": partition,
        "held_out_access": False,
        "m_sufficiency_claimed": False,
        "integrated_analysis_performed": False,
    }
    return EVMappedProfileBatch(
        member_ids=tuple(batch.member_ids),
        source_datetimes_utc=tuple(batch.datetimes_utc),
        source_datetimes_local=tuple(batch.datetimes_local),
        target_datetimes_utc=target_utc,
        target_datetimes_local=target_local,
        demands_kw=np.array(batch.demands_kw, copy=True),
        batch_seed=batch.batch_seed,
        mapping_provenance=provenance,
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
class ProposedLocalChargePointCount:
    """Proposed local Outlook count kept out of executable adoption scenarios."""

    year: int
    scenario: str
    location: str
    value: float
    rounded_count: int
    area_type: str
    area_identifier: str
    source_id: str
    response_sha256: str
    status: str


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


@dataclass(frozen=True)
class EVLibraryCandidateBatchRef:
    """Manifest-only reference to one candidate EV source batch."""

    library_id: str
    component_id: str
    seed: int
    n_profiles: int
    n_timesteps: int
    processed_path: str
    processed_sha256_file: str
    manifest_path: str
    distinct_member_count: int
    capacity_class: str | None = None
    cp_capacity_kw: int | None = None
    request_sha256: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_string(self.library_id, "library_id")
        _require_non_empty_string(self.component_id, "component_id")
        if self.component_id not in {EV_HOME_COMPONENT, EV_PUBLIC_COMPONENT}:
            raise ValueError("EV integration batch component_id must be ev_home or ev_public")
        _require_int(self.seed, "seed")
        profiles = _require_int(self.n_profiles, "n_profiles")
        timesteps = _require_int(self.n_timesteps, "n_timesteps")
        distinct = _require_int(self.distinct_member_count, "distinct_member_count")
        if profiles <= 0:
            raise ValueError("n_profiles must be positive")
        if timesteps != EXPECTED_FULL_YEAR_STEPS:
            raise ValueError(f"EV candidate batches must contain {EXPECTED_FULL_YEAR_STEPS} timesteps")
        if distinct != profiles:
            raise ValueError("EV candidate batches must record all returned members as distinct")
        _require_non_empty_string(self.processed_path, "processed_path")
        _require_sha256(self.processed_sha256_file, "processed_sha256_file")
        _require_non_empty_string(self.manifest_path, "manifest_path")
        if self.cp_capacity_kw is not None and _require_int(self.cp_capacity_kw, "cp_capacity_kw") <= 0:
            raise ValueError("cp_capacity_kw must be positive")
        if self.request_sha256 is not None:
            _require_sha256(self.request_sha256, "request_sha256")

    @property
    def member_id_pattern(self) -> str:
        return f"profile_{self.seed}_<returned_profile_index:03d>"

    def manifest_record(self) -> dict[str, int | str | None | list[int]]:
        return {
            "library_id": self.library_id,
            "component_id": self.component_id,
            "seed": self.seed,
            "n_profiles": self.n_profiles,
            "n_timesteps": self.n_timesteps,
            "processed_path": self.processed_path,
            "processed_sha256_file": self.processed_sha256_file,
            "manifest_path": self.manifest_path,
            "distinct_member_count": self.distinct_member_count,
            "capacity_class": self.capacity_class,
            "cp_capacity_kw": self.cp_capacity_kw,
            "request_sha256": self.request_sha256,
            "member_id_pattern": self.member_id_pattern,
            "returned_profile_index_range": [0, self.n_profiles - 1],
        }


@dataclass(frozen=True)
class EVLibraryIntegrationArtifact:
    """Candidate-only EV library description for later IC-1 adapters."""

    library_id: str
    component_id: str
    source_manifest_path: str
    data_id: str
    governing_decisions: tuple[str, ...]
    candidate_batches: tuple[EVLibraryCandidateBatchRef, ...]
    candidate_member_count: int
    held_out_member_count: int
    held_out_unopened_for_adequacy: bool
    library_adequacy_proven: bool
    calendar_assumption: dict[str, int | str]
    sampling_policy: dict[str, bool | str]

    def __post_init__(self) -> None:
        _require_non_empty_string(self.library_id, "library_id")
        _require_non_empty_string(self.component_id, "component_id")
        _require_non_empty_string(self.source_manifest_path, "source_manifest_path")
        _require_non_empty_string(self.data_id, "data_id")
        if not self.governing_decisions:
            raise ValueError("EV library artifact must record governing decisions")
        if not self.candidate_batches:
            raise ValueError("EV library artifact must include candidate batches")
        if self.candidate_member_count != sum(batch.n_profiles for batch in self.candidate_batches):
            raise ValueError("candidate_member_count must equal candidate batch profile total")
        if self.held_out_member_count < 0:
            raise ValueError("held_out_member_count must be non-negative")
        if not self.held_out_unopened_for_adequacy:
            raise ValueError("EV held-out batches must remain unopened for adequacy")
        if self.library_adequacy_proven:
            raise ValueError("EV integration readiness must not certify library adequacy")

    @property
    def candidate_seeds(self) -> tuple[int, ...]:
        return tuple(batch.seed for batch in self.candidate_batches)

    def manifest_record(self) -> dict[str, object]:
        return {
            "library_id": self.library_id,
            "component_id": self.component_id,
            "source_manifest_path": self.source_manifest_path,
            "data_id": self.data_id,
            "governing_decisions": self.governing_decisions,
            "candidate_member_count": self.candidate_member_count,
            "candidate_seeds": self.candidate_seeds,
            "candidate_batches": tuple(batch.manifest_record() for batch in self.candidate_batches),
            "held_out_member_count": self.held_out_member_count,
            "held_out_unopened_for_adequacy": self.held_out_unopened_for_adequacy,
            "library_adequacy_proven": self.library_adequacy_proven,
            "calendar_assumption": self.calendar_assumption,
            "sampling_policy": self.sampling_policy,
        }


@dataclass(frozen=True)
class EVScenarioNodeAllocationRecord:
    """Approved A-014 node allocation record for one EV adoption scenario."""

    year: int
    scenario: str
    home_by_node: dict[str, int]
    public_by_node: dict[str, int]
    provenance: dict[str, str]

    @property
    def total_home_charge_points(self) -> int:
        return sum(self.home_by_node.values())

    @property
    def total_public_charge_points(self) -> int:
        return sum(self.public_by_node.values())

    def manifest_record(self) -> dict[str, object]:
        return {
            "year": self.year,
            "scenario": self.scenario,
            "home_charge_points": self.total_home_charge_points,
            "public_charge_points": self.total_public_charge_points,
            "home_by_node": dict(sorted(self.home_by_node.items())),
            "public_by_node": dict(sorted(self.public_by_node.items())),
            "provenance": dict(sorted(self.provenance.items())),
        }


@dataclass(frozen=True)
class EVIntegrationReadinessArtifact:
    """Complete EV artifact handoff description for future IC-1 consumption."""

    libraries: tuple[EVLibraryIntegrationArtifact, ...]
    node_allocations: tuple[EVScenarioNodeAllocationRecord, ...]
    allocation_method_id: str
    scenario_config_path: str
    calendar_mapping: dict[str, str | int | bool]
    policy: dict[str, bool | str]

    def __post_init__(self) -> None:
        if not self.libraries:
            raise ValueError("EV integration readiness requires at least one library")
        component_ids = {library.component_id for library in self.libraries}
        if component_ids != {EV_HOME_COMPONENT, EV_PUBLIC_COMPONENT}:
            raise ValueError("EV integration readiness requires home and public EV libraries")
        if not self.node_allocations:
            raise ValueError("EV integration readiness requires approved node allocations")
        if self.allocation_method_id != "A-014":
            raise ValueError("EV integration readiness requires A-014 allocations")
        if self.policy.get("held_out_access") is not False:
            raise ValueError("EV integration readiness must block held-out access")
        if self.policy.get("m_sufficiency_claimed") is not False:
            raise ValueError("EV integration readiness must not claim M sufficiency")
        if self.policy.get("integrated_analysis_performed") is not False:
            raise ValueError("EV integration readiness must not include integrated analysis")

    def manifest_record(self) -> dict[str, object]:
        totals = {
            allocation.scenario: {
                "home": allocation.total_home_charge_points,
                "public": allocation.total_public_charge_points,
            }
            for allocation in self.node_allocations
        }
        return {
            "schema_version": EV_INTEGRATION_READINESS_SCHEMA_VERSION,
            "artifact_type": "ev_to_ic1_integration_readiness",
            "libraries": tuple(library.manifest_record() for library in self.libraries),
            "allocation_method_id": self.allocation_method_id,
            "scenario_config_path": self.scenario_config_path,
            "scenario_totals": totals,
            "node_allocations": tuple(allocation.manifest_record() for allocation in self.node_allocations),
            "calendar_mapping": self.calendar_mapping,
            "policy": self.policy,
        }


@dataclass(frozen=True)
class EVCandidateChecksumExpectation:
    """Candidate processed-file digest expected before EV profile loading."""

    component_id: str
    library_id: str
    seed: int
    processed_path: str
    expected_sha256: str
    n_profiles: int
    n_timesteps: int
    capacity_class: str | None
    cp_capacity_kw: int | None

    def __post_init__(self) -> None:
        if self.component_id not in {EV_HOME_COMPONENT, EV_PUBLIC_COMPONENT}:
            raise ValueError("EV checksum expectation has unsupported component_id")
        _require_non_empty_string(self.library_id, "library_id")
        _require_int(self.seed, "seed")
        _require_non_empty_string(self.processed_path, "processed_path")
        _require_sha256(self.expected_sha256, "expected_sha256")
        _require_int(self.n_profiles, "n_profiles")
        _require_int(self.n_timesteps, "n_timesteps")
        if self.n_timesteps != EXPECTED_FULL_YEAR_STEPS:
            raise ValueError("EV checksum expectation must reference complete annual profiles")

    def manifest_record(self) -> dict[str, object]:
        return {
            "component_id": self.component_id,
            "library_id": self.library_id,
            "seed": self.seed,
            "processed_path": self.processed_path,
            "expected_sha256": self.expected_sha256,
            "n_profiles": self.n_profiles,
            "n_timesteps": self.n_timesteps,
            "capacity_class": self.capacity_class,
            "cp_capacity_kw": self.cp_capacity_kw,
        }


@dataclass(frozen=True)
class EVCandidateChecksumVerification:
    """Observed digest for one candidate processed file."""

    expectation: EVCandidateChecksumExpectation
    observed_sha256: str
    byte_size: int

    def __post_init__(self) -> None:
        _require_sha256(self.observed_sha256, "observed_sha256")
        _require_int(self.byte_size, "byte_size")
        if self.byte_size <= 0:
            raise ValueError("EV checksum verification requires a non-empty file")
        if self.observed_sha256 != self.expectation.expected_sha256:
            raise ValueError(
                f"EV candidate checksum mismatch for {self.expectation.processed_path}"
            )

    def manifest_record(self) -> dict[str, object]:
        record = self.expectation.manifest_record()
        record.update(
            {
                "observed_sha256": self.observed_sha256,
                "byte_size": self.byte_size,
                "checksum_verified": True,
            }
        )
        return record


@dataclass(frozen=True)
class EVPlanningCalendarMappingExpectation:
    """Guardrail describing the source-to-planning-year calendar handoff."""

    source_calendar_local_year: int
    target_planning_year: int
    n_timesteps: int
    step_seconds: int
    timezone: str
    mapping_status: str
    profile_loading_allowed_before_mapping: bool

    def __post_init__(self) -> None:
        if self.source_calendar_local_year != 2025:
            raise ValueError("EV source profiles must remain on the 2025 generator calendar")
        if self.target_planning_year != 2035:
            raise ValueError("EV IC-1 readiness currently targets the G0-A4 2035 planning year")
        if self.n_timesteps != EXPECTED_FULL_YEAR_STEPS:
            raise ValueError("EV calendar mapping requires a complete 15-minute annual calendar")
        if self.step_seconds != 900:
            raise ValueError("EV calendar mapping requires 900-second cadence")
        if self.timezone != LOCAL_TIMEZONE:
            raise ValueError("EV calendar mapping must preserve the Europe/Amsterdam source zone")
        if not self.mapping_status:
            raise ValueError("EV calendar mapping status is required")
        if self.profile_loading_allowed_before_mapping:
            raise ValueError("EV profiles must not be loaded into IC-1 before calendar mapping")

    def manifest_record(self) -> dict[str, object]:
        return {
            "source_calendar_local_year": self.source_calendar_local_year,
            "target_planning_year": self.target_planning_year,
            "n_timesteps": self.n_timesteps,
            "step_seconds": self.step_seconds,
            "timezone": self.timezone,
            "mapping_status": self.mapping_status,
            "profile_loading_allowed_before_mapping": self.profile_loading_allowed_before_mapping,
            "guardrail": (
                "Complete EV source members must be mapped to the common planning-year "
                "calendar before IC-1 aggregation; this packet does not choose the "
                "mapping algorithm or produce trajectories."
            ),
        }


def load_ev_integration_readiness_record(path: Path) -> dict[str, Any]:
    """Load the committed EV-to-IC-1 readiness artifact and enforce safe policy flags."""

    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise ValueError("EV readiness artifact must be a mapping")
    if record.get("schema_version") != EV_INTEGRATION_READINESS_SCHEMA_VERSION:
        raise ValueError("Unsupported EV readiness artifact schema_version")
    if record.get("artifact_type") != "ev_to_ic1_integration_readiness":
        raise ValueError("Unexpected EV readiness artifact_type")
    policy = record.get("policy")
    if not isinstance(policy, dict):
        raise ValueError("EV readiness artifact must include policy")
    if policy.get("held_out_access") is not False:
        raise ValueError("EV readiness artifact must block held-out access")
    if policy.get("candidate_profiles_opened") is not False:
        raise ValueError("EV readiness artifact must not mark candidate profiles opened")
    if policy.get("integrated_analysis_performed") is not False:
        raise ValueError("EV readiness artifact must not include integrated analysis")
    if policy.get("m_sufficiency_claimed") is not False:
        raise ValueError("EV readiness artifact must not claim M sufficiency")
    return record


def ev_candidate_checksum_expectations(
    readiness_record: Mapping[str, Any],
) -> tuple[EVCandidateChecksumExpectation, ...]:
    """Derive candidate-only processed-file checksum expectations from readiness metadata."""

    libraries = readiness_record.get("libraries")
    if not isinstance(libraries, (list, tuple)):
        raise ValueError("EV readiness artifact must include library records")
    expectations: list[EVCandidateChecksumExpectation] = []
    for library in libraries:
        if not isinstance(library, dict):
            raise ValueError("EV readiness library records must be mappings")
        library_id = str(library.get("library_id", ""))
        component_id = str(library.get("component_id", ""))
        batches = library.get("candidate_batches", [])
        if not isinstance(batches, (list, tuple)):
            raise ValueError("EV readiness candidate_batches must be a sequence")
        for batch in batches:
            if not isinstance(batch, dict):
                raise ValueError("EV readiness candidate batches must be mappings")
            path = str(batch.get("processed_path", ""))
            # Only processed candidate NPZ files are eligible for this preflight:
            # raw API responses and held-out paths stay out of the IC-1 adapter lane.
            if "held_out" in path or "quarantined" in path or "/raw/" in path.replace("\\", "/"):
                raise ValueError("EV checksum expectations must reference candidate processed files only")
            expectations.append(
                EVCandidateChecksumExpectation(
                    component_id=component_id,
                    library_id=library_id,
                    seed=_require_int(batch.get("seed"), "seed"),
                    processed_path=path,
                    expected_sha256=str(batch.get("processed_sha256_file", "")),
                    n_profiles=_require_int(batch.get("n_profiles"), "n_profiles"),
                    n_timesteps=_require_int(batch.get("n_timesteps"), "n_timesteps"),
                    capacity_class=(
                        None if batch.get("capacity_class") is None else str(batch["capacity_class"])
                    ),
                    cp_capacity_kw=(
                        None
                        if batch.get("cp_capacity_kw") is None
                        else _require_int(batch.get("cp_capacity_kw"), "cp_capacity_kw")
                    ),
                )
            )
    if not expectations:
        raise ValueError("EV readiness artifact must expose candidate checksum expectations")
    return tuple(expectations)


def verify_ev_candidate_checksums(
    readiness_record: Mapping[str, Any],
    *,
    base_dir: Path,
) -> tuple[EVCandidateChecksumVerification, ...]:
    """Verify expected candidate file digests without loading EV profile arrays."""

    verifications: list[EVCandidateChecksumVerification] = []
    for expectation in ev_candidate_checksum_expectations(readiness_record):
        path = base_dir / Path(expectation.processed_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        verifications.append(
            EVCandidateChecksumVerification(
                expectation=expectation,
                observed_sha256=_sha256_file(path),
                byte_size=path.stat().st_size,
            )
        )
    return tuple(verifications)


def ev_planning_calendar_mapping_expectation(
    readiness_record: Mapping[str, Any],
) -> EVPlanningCalendarMappingExpectation:
    """Return the EV calendar guardrail required before IC-1 profile use."""

    mapping = readiness_record.get("calendar_mapping")
    if not isinstance(mapping, dict):
        raise ValueError("EV readiness artifact must include calendar_mapping")
    return EVPlanningCalendarMappingExpectation(
        source_calendar_local_year=_require_int(
            mapping.get("profile_generator_calendar_local_year"),
            "profile_generator_calendar_local_year",
        ),
        target_planning_year=_require_int(mapping.get("planning_year"), "planning_year"),
        n_timesteps=_require_int(mapping.get("n_timesteps"), "n_timesteps"),
        step_seconds=_require_int(mapping.get("step_seconds"), "step_seconds"),
        timezone=str(mapping.get("timezone", "")),
        mapping_status=str(mapping.get("planning_year_mapping_status", "")),
        profile_loading_allowed_before_mapping=False,
    )


def ev_ic1_adapter_guardrail_packet(readiness_record: Mapping[str, Any]) -> dict[str, object]:
    """Build a manifestable EV adapter preflight packet for future IC-1 wiring."""

    expectations = ev_candidate_checksum_expectations(readiness_record)
    calendar = ev_planning_calendar_mapping_expectation(readiness_record)
    by_component: dict[str, int] = {}
    for item in expectations:
        by_component[item.component_id] = by_component.get(item.component_id, 0) + 1
    return {
        "schema_version": 1,
        "artifact_type": "ev_to_ic1_adapter_guardrails",
        "source_readiness_artifact": "data/metadata/ev_adoption/e2_s2_ev_integration_readiness.json",
        "candidate_checksum_expectation_count": len(expectations),
        "candidate_checksum_expectations_by_component": dict(sorted(by_component.items())),
        "candidate_member_count_by_component": dict(
            sorted(
                {
                    str(library["component_id"]): int(library["candidate_member_count"])
                    for library in readiness_record.get("libraries", [])
                    if isinstance(library, dict)
                }.items()
            )
        ),
        "calendar_mapping_expectation": calendar.manifest_record(),
        "ic1_use_blockers": [
            "deterministic planning-year calendar mapping must be approved/implemented",
            "candidate processed-file checksums must verify in the consuming worktree",
            "EV source-library adequacy must remain downstream of aggregated net-load analysis",
            "Q-5 still blocks event-based scientific analysis",
        ],
        "policy": {
            "candidate_libraries_only": True,
            "held_out_access": False,
            "profile_arrays_opened": False,
            "integrated_analysis_performed": False,
            "m_sufficiency_claimed": False,
        },
    }


def ev_ic1_candidate_adapter_artifact(
    readiness_record: Mapping[str, Any],
    *,
    checksum_verifications: Sequence[EVCandidateChecksumVerification] = (),
    verification_timestamp_utc: str | None = None,
) -> dict[str, object]:
    """Materialize candidate-only EV metadata and A-014 allocations for IC-1."""

    expectations = ev_candidate_checksum_expectations(readiness_record)
    expectation_keys = {
        (item.component_id, item.library_id, item.seed): item for item in expectations
    }
    verification_records: dict[tuple[str, str, int], dict[str, object]] = {}
    for verification in checksum_verifications:
        key = (
            verification.expectation.component_id,
            verification.expectation.library_id,
            verification.expectation.seed,
        )
        if key not in expectation_keys:
            raise ValueError("Checksum verification is not tied to a candidate expectation")
        verification_records[key] = verification.manifest_record()
    if checksum_verifications and len(verification_records) != len(expectations):
        raise ValueError("Checksum verification must cover every candidate batch")

    libraries = readiness_record.get("libraries")
    if not isinstance(libraries, (list, tuple)):
        raise ValueError("EV readiness artifact must include library records")
    materialized_libraries: list[dict[str, object]] = []
    for library in libraries:
        if not isinstance(library, dict):
            raise ValueError("EV readiness library records must be mappings")
        component_id = str(library.get("component_id", ""))
        library_id = str(library.get("library_id", ""))
        batches: list[dict[str, object]] = []
        for expectation in expectations:
            if expectation.component_id != component_id or expectation.library_id != library_id:
                continue
            key = (expectation.component_id, expectation.library_id, expectation.seed)
            checksum_record = verification_records.get(key)
            batches.append(
                {
                    "seed": expectation.seed,
                    "processed_path": expectation.processed_path,
                    "processed_sha256_file": expectation.expected_sha256,
                    "checksum_verification": (
                        checksum_record
                        if checksum_record is not None
                        else {
                            "checksum_verified": False,
                            "verification_required_before_loading": True,
                        }
                    ),
                    "n_profiles": expectation.n_profiles,
                    "n_timesteps": expectation.n_timesteps,
                    "returned_profile_index_range": [0, expectation.n_profiles - 1],
                    "member_id_pattern": f"profile_{expectation.seed}_<returned_profile_index:03d>",
                    "member_identity_fields": [
                        "component_id",
                        "library_id",
                        "batch_seed",
                        "returned_profile_index",
                    ],
                    "capacity_class": expectation.capacity_class,
                    "cp_capacity_kw": expectation.cp_capacity_kw,
                }
            )
        member_count = int(library.get("candidate_member_count", 0))
        materialized_libraries.append(
            {
                "component_id": component_id,
                "library_id": library_id,
                "candidate_member_count": member_count,
                "candidate_batch_count": len(batches),
                "candidate_batches": batches,
                "member_reference": {
                    "member_rows_materialized": False,
                    "compact_representation": (
                        "Members are the Cartesian expansion of each candidate batch seed "
                        "and returned_profile_index_range; no profile arrays are loaded."
                    ),
                    "member_id_rule": "profile_<batch_seed>_<returned_profile_index:03d>",
                },
            }
        )

    allocations = readiness_record.get("node_allocations")
    if not isinstance(allocations, (list, tuple)):
        raise ValueError("EV readiness artifact must include node_allocations")
    allocation_records: list[dict[str, object]] = []
    scenario_totals: dict[str, dict[str, int]] = {}
    for allocation in allocations:
        if not isinstance(allocation, dict):
            raise ValueError("EV node allocation records must be mappings")
        scenario = str(allocation.get("scenario", ""))
        home_by_node = _require_int_mapping(allocation.get("home_by_node"), "home_by_node")
        public_by_node = _require_int_mapping(allocation.get("public_by_node"), "public_by_node")
        if set(home_by_node) != set(public_by_node):
            raise ValueError("EV home/public allocations must cover the same IC-1 nodes")
        home_total = sum(home_by_node.values())
        public_total = sum(public_by_node.values())
        scenario_totals[scenario] = {"home": home_total, "public": public_total}
        allocation_records.append(
            {
                "scenario": scenario,
                "year": _require_int(allocation.get("year"), "year"),
                "node_count": len(home_by_node),
                "home_charge_points": home_total,
                "public_charge_points": public_total,
                "home_by_node": dict(sorted(home_by_node.items())),
                "public_by_node": dict(sorted(public_by_node.items())),
                "total_conservation_verified": True,
                "allocation_method_id": str(readiness_record.get("allocation_method_id", "")),
                "provenance": allocation.get("provenance", {}),
            }
        )

    calendar = ev_planning_calendar_mapping_expectation(readiness_record)
    verification_status = (
        "verified_in_agent_c_worktree"
        if checksum_verifications
        else "verification_required_before_loading"
    )
    return {
        "schema_version": 1,
        "artifact_type": "ev_to_ic1_candidate_adapter_artifact",
        "source_readiness_artifact": "data/metadata/ev_adoption/e2_s2_ev_integration_readiness.json",
        "source_guardrail_artifact": "data/metadata/ev_adoption/e2_s2_ev_ic1_adapter_guardrails.json",
        "planning_year": calendar.target_planning_year,
        "allocation_method_id": str(readiness_record.get("allocation_method_id", "")),
        "scenario_totals": dict(sorted(scenario_totals.items())),
        "node_allocations": sorted(allocation_records, key=lambda item: str(item["scenario"])),
        "candidate_libraries": sorted(
            materialized_libraries,
            key=lambda item: str(item["component_id"]),
        ),
        "checksum_preconditions": {
            "candidate_only": True,
            "candidate_processed_file_count": len(expectations),
            "verification_status": verification_status,
            "verification_timestamp_utc": verification_timestamp_utc,
            "verification_required_in_consuming_worktree_before_profile_loading": True,
            "profile_arrays_loaded": False,
        },
        "calendar_mapping_decision": {
            "status": "approved",
            "approved_rule_id": EV_CALENDAR_MAPPING_RULE_ID,
            "approved_rule_version": EV_CALENDAR_MAPPING_RULE_VERSION,
            "approved_option": "A_ordinal_timestep_mapping",
            "packet_path": "reports/e2_s2_ev_calendar_mapping_decision_packet.md",
            "expectation": calendar.manifest_record(),
        },
        "policy": {
            "candidate_libraries_only": True,
            "held_out_access": False,
            "m_sufficiency_claimed": False,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
        },
    }



def ev_ic1_candidate_member_reference_artifact(
    candidate_adapter_artifact: Mapping[str, Any],
    *,
    public_capacity_artifact: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    """Expand candidate EV batch ranges into IC-1 source-member references."""

    if candidate_adapter_artifact.get("artifact_type") != "ev_to_ic1_candidate_adapter_artifact":
        raise ValueError("Expected an EV-to-IC-1 candidate adapter artifact")
    policy = candidate_adapter_artifact.get("policy")
    if not isinstance(policy, dict) or policy.get("held_out_access") is not False:
        raise ValueError("Candidate member references must not include held-out access")
    if policy.get("m_sufficiency_claimed") is not False or policy.get("integrated_analysis_performed") is not False:
        raise ValueError("Candidate member references cannot claim M sufficiency or integrated analysis")
    checksum = candidate_adapter_artifact.get("checksum_preconditions")
    if not isinstance(checksum, dict) or checksum.get("candidate_only") is not True:
        raise ValueError("Candidate member references require candidate-only checksum preconditions")
    if checksum.get("profile_arrays_loaded") is not False:
        raise ValueError("Candidate member references must not load profile arrays")
    calendar = candidate_adapter_artifact.get("calendar_mapping_decision")
    if not isinstance(calendar, dict) or calendar.get("approved_rule_id") != EV_CALENDAR_MAPPING_RULE_ID:
        raise ValueError("Candidate member references require approved EV-CAL-001 mapping metadata")

    libraries = candidate_adapter_artifact.get("candidate_libraries")
    if not isinstance(libraries, (list, tuple)):
        raise ValueError("Candidate adapter artifact must include candidate_libraries")
    member_rows: list[dict[str, object]] = []
    member_counts_by_component: dict[str, int] = {}
    member_counts_by_public_capacity_class: dict[str, int] = {}
    seen_keys: set[tuple[str, str, str]] = set()
    for library in libraries:
        if not isinstance(library, dict):
            raise ValueError("Candidate library records must be mappings")
        component_id = _require_non_empty_string(library.get("component_id"), "component_id")
        library_id = _require_non_empty_string(library.get("library_id"), "library_id")
        batches = library.get("candidate_batches")
        if not isinstance(batches, (list, tuple)):
            raise ValueError("Candidate library records must include candidate_batches")
        for batch in batches:
            if not isinstance(batch, dict):
                raise ValueError("Candidate batch records must be mappings")
            checksum_record = batch.get("checksum_verification")
            if not isinstance(checksum_record, dict) or checksum_record.get("checksum_verified") is not True:
                raise ValueError("Candidate member references require verified candidate checksums")
            processed_sha = _require_sha256(batch.get("processed_sha256_file"), "processed_sha256_file")
            processed_path = _require_non_empty_string(batch.get("processed_path"), "processed_path")
            seed = _require_int(batch.get("seed"), "batch seed")
            n_profiles = _require_int(batch.get("n_profiles"), "n_profiles")
            n_timesteps = _require_int(batch.get("n_timesteps"), "n_timesteps")
            if n_timesteps != EXPECTED_FULL_YEAR_STEPS:
                raise ValueError("Candidate members must reference complete annual profiles")
            returned_range = batch.get("returned_profile_index_range")
            if not isinstance(returned_range, list) or len(returned_range) != 2:
                raise ValueError("Candidate batches must record returned_profile_index_range")
            start = _require_int(returned_range[0], "returned_profile_index start")
            stop = _require_int(returned_range[1], "returned_profile_index stop")
            if start != 0 or stop != n_profiles - 1:
                raise ValueError("Candidate returned profile range must cover every profile exactly once")
            capacity_class = batch.get("capacity_class")
            capacity_class_value = None if capacity_class is None else _require_non_empty_string(capacity_class, "capacity_class")
            cp_capacity_kw = batch.get("cp_capacity_kw")
            cp_capacity_value = None if cp_capacity_kw is None else _require_int(cp_capacity_kw, "cp_capacity_kw")
            for returned_profile_index in range(start, stop + 1):
                source_member_id = f"profile_{seed}_{returned_profile_index:03d}"
                key = (component_id, library_id, source_member_id)
                if key in seen_keys:
                    raise ValueError("Candidate source member IDs must be unique within a component library")
                seen_keys.add(key)
                row = {
                    "partition": "candidate",
                    "component_id": component_id,
                    "library_id": library_id,
                    "source_member_id": source_member_id,
                    "batch_seed": seed,
                    "returned_profile_index": returned_profile_index,
                    "capacity_class": capacity_class_value,
                    "cp_capacity_kw": cp_capacity_value,
                    "processed_path": processed_path,
                    "candidate_processed_sha256_file": processed_sha,
                    "n_timesteps": n_timesteps,
                    "calendar_mapping_rule_id": EV_CALENDAR_MAPPING_RULE_ID,
                    "calendar_mapping_rule_version": EV_CALENDAR_MAPPING_RULE_VERSION,
                    "source_calendar_id": EV_SOURCE_CALENDAR_ID,
                    "target_calendar_id": EV_TARGET_CALENDAR_ID,
                    "source_timestamp_index_policy": "target_index_i_uses_source_index_i",
                    "weekday_weekend_preserved": False,
                    "control_mode": "uncontrolled",
                }
                member_rows.append(row)
                member_counts_by_component[component_id] = member_counts_by_component.get(component_id, 0) + 1
                if component_id == EV_PUBLIC_COMPONENT:
                    if capacity_class_value is None:
                        raise ValueError("Public candidate members must record capacity_class")
                    member_counts_by_public_capacity_class[capacity_class_value] = (
                        member_counts_by_public_capacity_class.get(capacity_class_value, 0) + 1
                    )
    for library in libraries:
        if isinstance(library, dict):
            component_id = str(library.get("component_id"))
            expected = _require_int(library.get("candidate_member_count"), "candidate_member_count")
            if member_counts_by_component.get(component_id, 0) != expected:
                raise ValueError("Expanded member count does not match candidate library metadata")

    scenario_node_requirements = _ev_scenario_node_member_requirements(
        candidate_adapter_artifact,
        public_capacity_artifact=public_capacity_artifact,
    )
    return {
        "schema_version": 1,
        "artifact_type": "ev_ic1_candidate_member_reference",
        "source_candidate_adapter_artifact": "data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_adapter_artifact.json",
        "source_public_capacity_artifact": (
            "data/metadata/ev_adoption/e2_s2_public_set_b_capacity_allocation_readiness.json"
            if public_capacity_artifact is not None
            else None
        ),
        "planning_year": _require_int(candidate_adapter_artifact.get("planning_year"), "planning_year"),
        "candidate_member_count_by_component": dict(sorted(member_counts_by_component.items())),
        "public_candidate_member_count_by_capacity_class": dict(
            sorted(member_counts_by_public_capacity_class.items())
        ),
        "candidate_members": sorted(
            member_rows,
            key=lambda item: (
                str(item["component_id"]),
                str(item["capacity_class"]),
                int(item["batch_seed"]),
                int(item["returned_profile_index"]),
            ),
        ),
        "scenario_node_requirements": scenario_node_requirements,
        "calendar_mapping": {
            "status": "approved",
            "rule_id": EV_CALENDAR_MAPPING_RULE_ID,
            "rule_version": EV_CALENDAR_MAPPING_RULE_VERSION,
            "source_calendar_id": EV_SOURCE_CALENDAR_ID,
            "target_calendar_id": EV_TARGET_CALENDAR_ID,
            "source_timestamp_index_policy": "target_index_i_uses_source_index_i",
            "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
            "weekday_weekend_preserved": False,
        },
        "selection_boundary": {
            "replacement_rule_chosen": False,
            "component_stream_required": True,
            "sample_rows_materialized": False,
            "realization_selection_performed": False,
        },
        "policy": {
            "candidate_libraries_only": True,
            "held_out_access": False,
            "profile_arrays_loaded": False,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
            "m_sufficiency_claimed": False,
        },
    }


def _ev_scenario_node_member_requirements(
    candidate_adapter_artifact: Mapping[str, Any],
    *,
    public_capacity_artifact: Mapping[str, Any] | None,
) -> list[dict[str, object]]:
    allocations = candidate_adapter_artifact.get("node_allocations")
    if not isinstance(allocations, (list, tuple)):
        raise ValueError("Candidate adapter artifact must include node_allocations")
    public_by_scenario: dict[str, dict[str, dict[str, int]]] = {}
    if public_capacity_artifact is not None:
        if public_capacity_artifact.get("artifact_type") != "ev_public_set_b_capacity_allocation_readiness":
            raise ValueError("Expected public Set B capacity allocation readiness artifact")
        policy = public_capacity_artifact.get("policy")
        if not isinstance(policy, dict) or policy.get("held_out_access") is not False:
            raise ValueError("Public capacity artifact must not include held-out access")
        scenario_allocations = public_capacity_artifact.get("scenario_allocations")
        if not isinstance(scenario_allocations, (list, tuple)):
            raise ValueError("Public capacity artifact must include scenario_allocations")
        for item in scenario_allocations:
            if not isinstance(item, dict):
                raise ValueError("Public scenario allocation records must be mappings")
            scenario = _require_non_empty_string(item.get("scenario"), "scenario")
            by_node_raw = item.get("public_by_node_by_capacity_class")
            if not isinstance(by_node_raw, dict):
                raise ValueError("Public capacity artifact must include node-by-class public counts")
            public_by_scenario[scenario] = {
                _require_non_empty_string(node_id, "node_id"): _require_int_mapping(value, "public_by_capacity_class")
                for node_id, value in by_node_raw.items()
            }
    records: list[dict[str, object]] = []
    for allocation in allocations:
        if not isinstance(allocation, dict):
            raise ValueError("EV node allocation records must be mappings")
        scenario = _require_non_empty_string(allocation.get("scenario"), "scenario")
        home_by_node = _require_int_mapping(allocation.get("home_by_node"), "home_by_node")
        public_by_node = _require_int_mapping(allocation.get("public_by_node"), "public_by_node")
        if set(home_by_node) != set(public_by_node):
            raise ValueError("Home and public node requirements must cover the same nodes")
        public_capacity_by_node = public_by_scenario.get(scenario)
        if public_capacity_artifact is not None and public_capacity_by_node is None:
            raise ValueError("Public capacity artifact does not cover every scenario")
        for node_id in sorted(home_by_node):
            capacity_counts = None
            if public_capacity_by_node is not None:
                capacity_counts = public_capacity_by_node.get(node_id)
                if capacity_counts is None:
                    raise ValueError("Public capacity artifact does not cover every node")
                if sum(capacity_counts.values()) != public_by_node[node_id]:
                    raise ValueError("Public capacity-class requirements must conserve node public totals")
            records.append(
                {
                    "scenario": scenario,
                    "year": _require_int(allocation.get("year"), "year"),
                    "node_id": node_id,
                    "home_required_members": home_by_node[node_id],
                    "public_required_members": public_by_node[node_id],
                    "public_required_members_by_capacity_class": capacity_counts,
                    "allocation_method_id": str(allocation.get("allocation_method_id", "")),
                    "source_type": "required_member_counts_not_realization_draws",
                }
            )
    return sorted(records, key=lambda item: (str(item["scenario"]), str(item["node_id"])))

def ev_downstream_adequacy_criterion_packet() -> dict[str, object]:
    """Return the unsigned E3.S2a EV library-adequacy criterion packet."""

    return {
        "schema_version": 1,
        "artifact_type": "ev_downstream_adequacy_criterion_packet",
        "task_id": "E3.S2a",
        "status": "pi_decision_required_before_held_out_use",
        "governing_decisions": [
            "EV-003",
            "EV-005",
            "EV-007A",
            "EV-008A",
            "EV-CAL-001",
            "ALEA-002",
            "G0-A3",
            "G0-A4",
        ],
        "purpose": (
            "Frame the downstream, integrated net-load criterion that must be signed "
            "before EV held-out batches can certify finite-library adequacy."
        ),
        "recommended_option_id": "A_decision_stability_plus_event_probability_band",
        "options": [
            {
                "id": "A_decision_stability_plus_event_probability_band",
                "status": "recommended_unsigned",
                "criterion_family": "integrated_event_probability_and_decision_stability",
                "description": (
                    "Compare candidate-library and held-out-library results after full IC-1 net-load "
                    "aggregation and event detection. Require the reinforcement decision class and "
                    "alpha-indexed probability bounds to remain stable within a PI-signed tolerance."
                ),
                "why_defensible": (
                    "ALEA-002 says adequacy belongs downstream of aggregated net load, and the paper's "
                    "decision depends on alpha-indexed event probability bounds rather than EV-only tails."
                ),
                "requires_pi_values": [
                    "probability_bound_tolerance_by_alpha",
                    "decision_stability_rule_near_pcrit",
                    "minimum_replicate_or_crn_design",
                ],
            },
            {
                "id": "B_loading_quantile_diagnostic_plus_decision_check",
                "status": "unsigned_alternative",
                "criterion_family": "integrated_loading_distribution_diagnostic",
                "description": (
                    "Use full-year integrated transformer-loading quantile or episode-count diagnostics "
                    "as a predeclared supplement, but keep final adequacy tied to event/decision stability."
                ),
                "why_defensible": (
                    "It can reveal source-library tail mismatch before final event counts, but by itself "
                    "would violate ALEA-002 if treated as the adequacy decision."
                ),
                "requires_pi_values": [
                    "loading_quantile_levels",
                    "diagnostic_tolerance",
                    "whether_diagnostic_is_blocking_or_advisory",
                ],
            },
            {
                "id": "C_component_profile_tail_only",
                "status": "not_recommended_unsigned",
                "criterion_family": "component_only_diagnostic",
                "description": (
                    "Compare EV-only profile annual energy, peak, or sustained-load tails between "
                    "candidate and held-out libraries."
                ),
                "why_not_primary": (
                    "ALEA-002 explicitly rejects component-only adequacy certification because congestion "
                    "is determined after baseline, EV, HP, PV, adoption, flexibility, and grid evaluation."
                ),
                "allowed_role": "source_quality_diagnostic_only",
            },
        ],
        "preconditions_before_any_held_out_opening": [
            "IC-1 can aggregate baseline, EV, HP, PV, adoption, and flexibility on one common calendar",
            "EV-CAL-001 mapping is applied to loaded candidate and held-out trajectories",
            "RNG-001 component streams and CRN design are fixed for the adequacy comparison",
            "EV-005 within-realization replacement policy or no-replacement rule is signed for the tested cohort sizes",
            "G0-A3 event threshold semantics are implemented by the downstream evaluator",
            "PI signs numerical tolerances before held-out adequacy results are inspected",
        ],
        "suggested_test_checks_after_pi_approval": [
            "candidate_and_held_out_partitions_remain_disjoint",
            "criterion_tolerance_loaded_from_signed_config",
            "component_profile_arrays_not_loaded_before_authorized_step",
            "held_out_results_have_runner_manifest",
            "alpha_indexed_bounds_not_defuzzified",
            "criterion_failure_blocks_m_sufficiency_claim",
        ],
        "non_claims": {
            "criterion_signed": False,
            "held_out_access": False,
            "profile_arrays_loaded": False,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
            "m_sufficiency_claimed": False,
            "manuscript_numbers_produced": False,
        },
    }


def ev005_within_realization_replacement_policy_packet() -> dict[str, object]:
    """Return the unsigned EV-005 replacement-policy decision packet."""

    return {
        "schema_version": 1,
        "artifact_type": "ev005_within_realization_replacement_policy_packet",
        "decision_id": "EV-005B",
        "task_id": "E2.S2",
        "status": "pi_decision_required_before_sampling_policy_use",
        "governing_decisions": [
            "EV-003",
            "EV-005",
            "EV-007A",
            "EV-008A",
            "EV-CAL-001",
            "RNG-001",
            "ALEA-001",
            "ALEA-002",
        ],
        "purpose": (
            "Frame the within-realization EV source-member replacement rule that must be signed "
            "before IC-1 materializes EV charge-point selections from candidate libraries."
        ),
        "cohort_context": {
            "planning_year": 2035,
            "local_proxy": "Alkmaar GM0361",
            "scenario_totals": {
                "low": {"home_charge_points": 7992, "public_charge_points": 4183},
                "middle": {"home_charge_points": 9386, "public_charge_points": 5127},
                "high": {"home_charge_points": 10343, "public_charge_points": 6138},
            },
            "public_capacity_class_totals": {
                "low": {"public_11kw": 1046, "public_13kw": 1046, "public_15kw": 1046, "public_22kw": 1045},
                "middle": {"public_11kw": 1282, "public_13kw": 1282, "public_15kw": 1282, "public_22kw": 1281},
                "high": {"public_11kw": 1535, "public_13kw": 1535, "public_15kw": 1534, "public_22kw": 1534},
            },
        },
        "candidate_library_context": {
            "home_candidate_members": 1000,
            "public_candidate_members_total": 1200,
            "public_candidate_members_by_capacity_class": {
                "public_11kw": 300,
                "public_13kw": 300,
                "public_15kw": 300,
                "public_22kw": 300,
            },
            "candidate_library_sufficiency_claimed": False,
        },
        "feasibility_findings": {
            "whole_grid_no_replacement_feasible_for_home": False,
            "whole_grid_no_replacement_feasible_for_public_capacity_classes": False,
            "reason": (
                "The approved 2035 Alkmaar cohorts exceed the candidate member counts: home K is "
                "7,992-10,343 versus M=1,000, and each public capacity class has K above 1,000 "
                "versus M=300. Whole-grid no-replacement sampling would therefore fail before "
                "any downstream adequacy test."
            ),
        },
        "recommended_option_id": "A_charge_point_level_with_replacement",
        "options": [
            {
                "id": "A_charge_point_level_with_replacement",
                "status": "recommended_unsigned",
                "replacement": True,
                "selection_unit": "physical_charge_point",
                "selection_scope": "scenario_node_component_capacity_class",
                "rule": (
                    "For each realization, draw each physical charge point independently with replacement "
                    "from the verified candidate library for its component and, for public charging, its "
                    "EV-008A capacity class. Preserve selection order, multiplicity, source_member_id, "
                    "batch_seed, returned_profile_index, processed checksum, and RNG-001 component-stream identity."
                ),
                "why_defensible": (
                    "It is executable for K greater than M, matches the usual empirical-bootstrap interpretation, "
                    "and keeps finite-library adequacy separate through EV-005 downstream candidate/held-out checks."
                ),
                "requires_pi_signoff": [
                    "accept duplicate source members within one realization as bootstrap multiplicities",
                    "confirm public capacity-class sampling uses each class-specific candidate library",
                    "confirm manifests must record per-selection multiplicity and component-stream identity",
                ],
            },
            {
                "id": "B_whole_grid_without_replacement",
                "status": "not_executable_for_approved_2035_counts",
                "replacement": False,
                "selection_unit": "physical_charge_point",
                "selection_scope": "whole_grid_component_capacity_class",
                "why_not_recommended": (
                    "Approved home and public capacity-class cohort sizes exceed their available candidate "
                    "member counts, so this rule would block all 2035 Alkmaar branches unless the source "
                    "library were expanded by an order of magnitude and then re-tested for adequacy."
                ),
            },
            {
                "id": "C_node_local_without_replacement_with_cross_node_reuse",
                "status": "unsigned_alternative_not_recommended",
                "replacement": False,
                "selection_unit": "physical_charge_point",
                "selection_scope": "node_component_capacity_class_only",
                "why_not_recommended": (
                    "It can avoid duplicates inside one node when node-level K is small, but the same source "
                    "member may still appear at many nodes in the same realization. That hidden reuse rule is "
                    "harder to explain than explicit bootstrap multiplicity and does not remove finite-library uncertainty."
                ),
            },
        ],
        "implementation_expectations_after_approval": [
            "sampling uses RNG-001 ComponentStream objects supplied by the whole-system realization context",
            "EV home sampling requires the ev_home component stream and public sampling requires ev_public",
            "candidate processed checksums are verified in the consuming worktree before profile arrays load",
            "held-out and quarantined partitions remain inaccessible until traceable E3.S2a authorization exists",
            "selection manifests record scenario, node_id, component_id, capacity_class, selection_index, source_member_id, batch_seed, returned_profile_index, stream_id, and replacement flag",
        ],
        "non_claims": {
            "policy_signed": False,
            "held_out_access": False,
            "profile_arrays_loaded": False,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
            "m_sufficiency_claimed": False,
            "manuscript_numbers_produced": False,
        },
    }
def a014_node_weights_from_load_table(
    load_table: Any,
    *,
    node_id_template: str = "load_{source_load_index:03d}",
) -> tuple[tuple[str, float], ...]:
    """Return A-014 node weights from a pandapower ``net.load`` table."""

    if not hasattr(load_table, "iterrows") or "p_mw" not in load_table:
        raise ValueError("A-014 load table must provide a p_mw column")
    records: list[tuple[str, float]] = []
    for source_load_index, row in load_table.iterrows():
        if "in_service" in load_table and not bool(row["in_service"]):
            continue
        index = _require_int(int(source_load_index), "source_load_index")
        node_id = node_id_template.format(source_load_index=index)
        weight = float(row["p_mw"])
        if not np.isfinite(weight) or weight < 0.0:
            raise ValueError("A-014 load weights must be finite and non-negative")
        records.append((node_id, weight))
    _validate_weight_pairs(records)
    return tuple(records)


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
    proposed_workflow = config.get("local_count_workflow")
    if proposed_workflow is not None:
        _validate_local_count_workflow(proposed_workflow, outlook_id=outlook_id)
    allocation = config.get("allocation")
    if not isinstance(allocation, dict):
        raise ValueError("Adoption scenario config must include allocation settings")
    if allocation.get("method_id") != allocation_id:
        raise ValueError("allocation.method_id must match source_ids.local_allocation_assumption")
    if allocation.get("status") not in {
        "blocked",
        "proposed",
        "approved",
        "approved_after_local_totals",
    }:
        raise ValueError("allocation status is not recognized")
    weights = allocation.get("node_weights")
    if weights is None:
        if allocation.get("status") == "approved":
            raise ValueError("approved A-014 allocation requires explicit node_weights")
        source = allocation.get("node_weight_source")
        if not isinstance(source, dict) or source.get("method_id") != allocation_id:
            raise ValueError("allocation must provide node_weights or an A-014 node_weight_source")
    else:
        _validate_node_weight_records(weights)
    local = config.get("local_grid_scenarios")
    if not isinstance(local, dict):
        raise ValueError("local_grid_scenarios must be present")
    if local.get("status") not in {
        "blocked",
        "proposed",
        "approved",
        "pending_local_cluster_selection",
    }:
        raise ValueError("local_grid_scenarios status is not recognized")
    scenarios = local.get("scenarios")
    if not isinstance(scenarios, list):
        raise ValueError("local_grid_scenarios.scenarios must be a list")
    if local.get("status") != "approved" and scenarios:
        raise ValueError("Local-grid scenarios may contain counts only after local totals are approved")
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


def proposed_local_charge_point_counts(
    config: dict[str, Any],
) -> tuple[ProposedLocalChargePointCount, ...]:
    """Return auditable proposed local counts without approving them for use."""

    validate_adoption_scenarios_config(config)
    workflow = config.get("local_count_workflow")
    if not isinstance(workflow, dict):
        return ()
    outlook_id = str(config["source_ids"]["national_outlook_projection"])
    return tuple(
        _proposed_local_count_from_mapping(
            item,
            outlook_id=outlook_id,
            workflow=workflow,
        )
        for item in workflow["proposed_2035_counts"]
    )


def adoption_scenarios(config: dict[str, Any]) -> tuple[ChargePointScenario, ...]:
    """Return validated local-grid charge-point scenarios from config data."""

    validate_adoption_scenarios_config(config)
    if config["local_grid_scenarios"].get("status") != "approved":
        raise ValueError("Local-grid charge-point scenarios require EV-007 local totals before use")
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


def public_set_b_capacity_class_totals(
    total_public_charge_points: int,
    capacity_mix: Sequence[tuple[str, int, float]] = EV_PUBLIC_SET_B_CAPACITY_MIX,
) -> dict[str, int]:
    """Split a public charge-point total across signed EV-008A capacity classes."""

    validated = _validate_public_set_b_capacity_mix(capacity_mix)
    weights = tuple((capacity_class, share) for capacity_class, _, share in validated)
    return allocate_charge_points_to_nodes(total_public_charge_points, weights)


def allocate_public_charge_points_by_capacity_class(
    public_by_node: Mapping[str, int],
    capacity_mix: Sequence[tuple[str, int, float]] = EV_PUBLIC_SET_B_CAPACITY_MIX,
) -> dict[str, dict[str, int]]:
    """Allocate public node counts into EV-008A capacity classes deterministically."""

    node_totals = _require_int_mapping(dict(public_by_node), "public_by_node")
    validated = _validate_public_set_b_capacity_mix(capacity_mix)
    total_public = sum(node_totals.values())
    class_totals = public_set_b_capacity_class_totals(total_public, validated)
    class_ids = tuple(capacity_class for capacity_class, _, _ in validated)
    total_share = sum(share for _, _, share in validated)
    cells: dict[tuple[str, str], int] = {}
    row_remaining = dict(node_totals)
    col_remaining = dict(class_totals)
    fractional_ranks: list[tuple[float, str, str]] = []

    for node_id in sorted(node_totals):
        for capacity_class, _, share in validated:
            quota = node_totals[node_id] * share / total_share
            floor = int(np.floor(quota))
            cells[(node_id, capacity_class)] = floor
            row_remaining[node_id] -= floor
            col_remaining[capacity_class] -= floor
            fractional_ranks.append((quota - floor, node_id, capacity_class))

    # The matrix rounding must conserve both the per-node public count and the
    # EV-008A class totals, otherwise IC-1 could silently sample the wrong mix.
    ranked = sorted(fractional_ranks, key=lambda item: (-item[0], item[1], item[2]))
    while any(value > 0 for value in row_remaining.values()):
        changed = False
        for _, node_id, capacity_class in ranked:
            if row_remaining[node_id] > 0 and col_remaining[capacity_class] > 0:
                cells[(node_id, capacity_class)] += 1
                row_remaining[node_id] -= 1
                col_remaining[capacity_class] -= 1
                changed = True
                if not any(value > 0 for value in row_remaining.values()):
                    break
        if not changed:
            raise ValueError("Unable to conserve public capacity-class allocation totals")

    if any(value != 0 for value in row_remaining.values()) or any(value != 0 for value in col_remaining.values()):
        raise ValueError("Public capacity-class allocation failed conservation checks")
    allocation = {
        node_id: {capacity_class: cells[(node_id, capacity_class)] for capacity_class in class_ids}
        for node_id in sorted(node_totals)
    }
    for node_id, row in allocation.items():
        if sum(row.values()) != node_totals[node_id]:
            raise ValueError("Public capacity-class allocation changed a node total")
    for capacity_class in class_ids:
        if sum(row[capacity_class] for row in allocation.values()) != class_totals[capacity_class]:
            raise ValueError("Public capacity-class allocation changed a class total")
    return allocation


def public_set_b_capacity_allocation_readiness_artifact(
    candidate_adapter_artifact: Mapping[str, Any],
) -> dict[str, object]:
    """Build candidate-only public Set B capacity allocations from IC-1 readiness metadata."""

    if candidate_adapter_artifact.get("artifact_type") != "ev_to_ic1_candidate_adapter_artifact":
        raise ValueError("Expected an EV-to-IC-1 candidate adapter artifact")
    policy = candidate_adapter_artifact.get("policy")
    if not isinstance(policy, dict) or policy.get("held_out_access") is not False:
        raise ValueError("Public Set B readiness must not use held-out profiles")
    if policy.get("m_sufficiency_claimed") is not False or policy.get("integrated_analysis_performed") is not False:
        raise ValueError("Public Set B readiness cannot include M sufficiency or integrated analysis")

    libraries = candidate_adapter_artifact.get("candidate_libraries")
    if not isinstance(libraries, (list, tuple)):
        raise ValueError("Candidate adapter artifact must include candidate_libraries")
    public_libraries = [
        library for library in libraries
        if isinstance(library, dict) and library.get("component_id") == EV_PUBLIC_COMPONENT
    ]
    if len(public_libraries) != 1:
        raise ValueError("Expected exactly one public EV candidate library")
    public_library = public_libraries[0]
    if public_library.get("library_id") != EV_PUBLIC_SET_B_LIBRARY_ID:
        raise ValueError("Public readiness requires the EV-008A Set B library")
    if public_library.get("candidate_member_count") != 1200:
        raise ValueError("EV-008A public Set B candidate member count must be 1200")

    class_metadata = _public_set_b_candidate_class_metadata(public_library)
    allocations = candidate_adapter_artifact.get("node_allocations")
    if not isinstance(allocations, (list, tuple)):
        raise ValueError("Candidate adapter artifact must include node_allocations")
    scenario_records: list[dict[str, object]] = []
    scenario_totals: dict[str, dict[str, int]] = {}
    for allocation in allocations:
        if not isinstance(allocation, dict):
            raise ValueError("Node allocation records must be mappings")
        scenario = _require_non_empty_string(allocation.get("scenario"), "scenario")
        public_by_node = _require_int_mapping(allocation.get("public_by_node"), "public_by_node")
        class_by_node = allocate_public_charge_points_by_capacity_class(public_by_node)
        class_totals = {
            capacity_class: sum(row[capacity_class] for row in class_by_node.values())
            for capacity_class, _, _ in EV_PUBLIC_SET_B_CAPACITY_MIX
        }
        public_total = sum(public_by_node.values())
        scenario_totals[scenario] = {"public": public_total, "classes": class_totals}
        scenario_records.append(
            {
                "scenario": scenario,
                "year": _require_int(allocation.get("year"), "year"),
                "node_count": len(public_by_node),
                "public_charge_points": public_total,
                "capacity_class_totals": class_totals,
                "public_by_node": dict(sorted(public_by_node.items())),
                "public_by_node_by_capacity_class": class_by_node,
                "node_total_conservation_verified": True,
                "capacity_class_total_conservation_verified": True,
            }
        )

    return {
        "schema_version": 1,
        "artifact_type": "ev_public_set_b_capacity_allocation_readiness",
        "decision_id": "EV-008A",
        "source_candidate_adapter_artifact": "data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_adapter_artifact.json",
        "planning_year": _require_int(candidate_adapter_artifact.get("planning_year"), "planning_year"),
        "allocation_method_id": candidate_adapter_artifact.get("allocation_method_id"),
        "library_id": EV_PUBLIC_SET_B_LIBRARY_ID,
        "component_id": EV_PUBLIC_COMPONENT,
        "capacity_mix": [
            {"capacity_class": capacity_class, "cp_capacity_kw": cp_capacity_kw, "share": share}
            for capacity_class, cp_capacity_kw, share in EV_PUBLIC_SET_B_CAPACITY_MIX
        ],
        "candidate_library": class_metadata,
        "scenario_totals": dict(sorted(scenario_totals.items())),
        "scenario_allocations": sorted(scenario_records, key=lambda item: str(item["scenario"])),
        "provenance_fields_required_later": [
            "scenario",
            "node_id",
            "capacity_class",
            "cp_capacity_kw",
            "component_id",
            "library_id",
            "batch_seed",
            "returned_profile_index",
            "source_member_id",
            "component_stream_id",
            "candidate_processed_sha256_file",
            "calendar_mapping_rule_id",
        ],
        "policy": {
            "candidate_libraries_only": True,
            "held_out_access": False,
            "profile_arrays_loaded": False,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
            "m_sufficiency_claimed": False,
            "public_smart_profiles_included": False,
            "dc_or_fast_charging_included": False,
        },
    }

def adoption_node_allocations(config: dict[str, Any]) -> tuple[NodeChargePointAllocation, ...]:
    """Derive deterministic per-node home/public charge-point allocations."""

    scenarios = adoption_scenarios(config)
    if not scenarios:
        raise ValueError("Local-grid charge-point counts require EV-007 local totals before allocation")
    if config["allocation"].get("status") != "approved":
        raise ValueError("Node charge-point allocation requires approved A-014 allocation settings")
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


def proposed_a014_allocation_preview(
    config: dict[str, Any],
    node_weights: Sequence[tuple[str, float]],
) -> tuple[NodeChargePointAllocation, ...]:
    """Preview A-014 allocations from proposed local counts without approving them."""

    validate_adoption_scenarios_config(config)
    if config["allocation"].get("status") != "approved_after_local_totals":
        raise ValueError("A-014 preview requires allocation status approved_after_local_totals")
    _validate_weight_pairs(node_weights)
    proposed_counts = proposed_local_charge_point_counts(config)
    grouped: dict[str, dict[str, ProposedLocalChargePointCount]] = {}
    for count in proposed_counts:
        grouped.setdefault(count.scenario, {})[count.location] = count
    allocations: list[NodeChargePointAllocation] = []
    for scenario in sorted(grouped):
        locations = grouped[scenario]
        if set(locations) != {"home", "public"}:
            raise ValueError("A-014 preview requires paired home and public counts")
        # This preview intentionally bypasses adoption_scenarios(): the counts
        # remain proposed, while A-014 rounding can still be audited in advance.
        allocations.append(
            NodeChargePointAllocation(
                year=2035,
                scenario=scenario,
                home_by_node=allocate_charge_points_to_nodes(
                    locations["home"].rounded_count,
                    node_weights,
                ),
                public_by_node=allocate_charge_points_to_nodes(
                    locations["public"].rounded_count,
                    node_weights,
                ),
            )
        )
    return tuple(allocations)


def ev_library_integration_artifact_from_manifest(
    manifest_path: Path,
    *,
    library_id: str,
    component_id: str,
    expected_candidate_members: int,
) -> EVLibraryIntegrationArtifact:
    """Return a candidate-only EV library reference without opening profiles."""

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("EV library manifest must be a mapping")
    batches: list[EVLibraryCandidateBatchRef] = []
    for item in manifest.get("batches", []):
        if not isinstance(item, dict):
            raise ValueError("EV library manifest batches must be mappings")
        partition = str(item.get("partition", ""))
        if partition in {"held_out", "quarantined_precriterion_diagnostic"}:
            continue
        if partition != "candidate":
            raise ValueError(f"Unsupported EV library partition {partition!r}")
        batches.append(
            EVLibraryCandidateBatchRef(
                library_id=library_id,
                component_id=component_id,
                seed=_require_int(item.get("seed"), "seed"),
                n_profiles=_require_int(item.get("n_profiles"), "n_profiles"),
                n_timesteps=_require_int(item.get("n_timesteps"), "n_timesteps"),
                processed_path=str(item.get("processed_path", "")),
                processed_sha256_file=str(item.get("processed_sha256_file", "")),
                manifest_path=str(item.get("manifest_path", "")),
                distinct_member_count=_require_int(
                    item.get("distinct_member_count"),
                    "distinct_member_count",
                ),
                capacity_class=(
                    None if item.get("capacity_class") is None else str(item["capacity_class"])
                ),
                cp_capacity_kw=(
                    None
                    if item.get("cp_capacity_kw") is None
                    else _require_int(item.get("cp_capacity_kw"), "cp_capacity_kw")
                ),
                request_sha256=(
                    None if item.get("request_sha256") is None else str(item["request_sha256"])
                ),
            )
        )
    candidate_members = _require_int(
        manifest.get("candidate_member_count"),
        "candidate_member_count",
    )
    if candidate_members != expected_candidate_members:
        raise ValueError("EV candidate member count does not match the expected approved library size")
    held_out_members = _require_int(
        manifest.get("held_out_member_count", 0),
        "held_out_member_count",
    )
    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        raise ValueError("EV library manifest must include policy")
    decisions = tuple(str(item) for item in policy.get("decisions", ()))
    return EVLibraryIntegrationArtifact(
        library_id=library_id,
        component_id=component_id,
        source_manifest_path=manifest_path.as_posix(),
        data_id=str(manifest.get("data_id", "")),
        governing_decisions=decisions,
        candidate_batches=tuple(batches),
        candidate_member_count=candidate_members,
        held_out_member_count=held_out_members,
        held_out_unopened_for_adequacy=bool(manifest.get("held_out_unopened_for_adequacy")),
        library_adequacy_proven=bool(manifest.get("library_adequacy_proven")),
        calendar_assumption=_ev_profile_calendar_assumption(),
        sampling_policy={
            "candidate_only": True,
            "held_out_access": False,
            "m_sufficiency_claimed": False,
            "within_realization_replacement_rule": "explicit_and_still_pending",
            "member_identity": "batch_seed_plus_returned_profile_index",
            "source_profile_files_opened": False,
        },
    )


def build_ev_integration_readiness_artifact(
    *,
    home_manifest_path: Path,
    public_manifest_path: Path,
    scenario_config_path: Path,
    expected_home_candidate_members: int = 1000,
    expected_public_candidate_members: int = 1200,
) -> EVIntegrationReadinessArtifact:
    """Build the EV-to-IC-1 readiness artifact from committed metadata only."""

    config = load_adoption_scenarios_config(scenario_config_path)
    allocations = adoption_node_allocations(config)
    scenarios = {item.scenario: item for item in adoption_scenarios(config)}
    allocation_records: list[EVScenarioNodeAllocationRecord] = []
    for allocation in allocations:
        scenario = scenarios[allocation.scenario]
        allocation_records.append(
            EVScenarioNodeAllocationRecord(
                year=allocation.year,
                scenario=allocation.scenario,
                home_by_node=allocation.home_by_node,
                public_by_node=allocation.public_by_node,
                provenance=scenario.provenance,
            )
        )

    return EVIntegrationReadinessArtifact(
        libraries=(
            ev_library_integration_artifact_from_manifest(
                home_manifest_path,
                library_id="A_home_vancar_cp_y2030",
                component_id=EV_HOME_COMPONENT,
                expected_candidate_members=expected_home_candidate_members,
            ),
            ev_library_integration_artifact_from_manifest(
                public_manifest_path,
                library_id="B_public_vancar_cp_y2030_equal_mix",
                component_id=EV_PUBLIC_COMPONENT,
                expected_candidate_members=expected_public_candidate_members,
            ),
        ),
        node_allocations=tuple(allocation_records),
        allocation_method_id=str(config["allocation"]["method_id"]),
        scenario_config_path=scenario_config_path.as_posix(),
        calendar_mapping={
            "profile_generator_calendar_local_year": 2025,
            "profile_generator_first_timestamp_local": "2025-01-01T00:00:00+01:00",
            "profile_generator_first_timestamp_utc": "2024-12-31T23:00:00+00:00",
            "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
            "step_seconds": 900,
            "timezone": LOCAL_TIMEZONE,
            "planning_year": 2035,
            "planning_year_mapping_status": "deterministic_calendar_mapping_required_before_ic1_results",
        },
        policy={
            "held_out_access": False,
            "candidate_profiles_opened": False,
            "integrated_analysis_performed": False,
            "threshold_or_event_analysis_performed": False,
            "p_e_estimated": False,
            "manuscript_numbers_produced": False,
            "m_sufficiency_claimed": False,
            "public_smart_profiles_included": False,
        },
    )


def write_ev_integration_readiness_artifact(
    artifact: EVIntegrationReadinessArtifact,
    path: Path,
) -> None:
    """Write a stable JSON EV readiness artifact."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        artifact.manifest_record(),
        sort_keys=True,
        indent=2,
        ensure_ascii=True,
    )
    path.write_text(payload + "\n", encoding="utf-8")


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


def _validate_public_set_b_capacity_mix(
    capacity_mix: Sequence[tuple[str, int, float]],
) -> tuple[tuple[str, int, float], ...]:
    if not capacity_mix:
        raise ValueError("EV-008A capacity mix must be non-empty")
    validated: list[tuple[str, int, float]] = []
    seen_classes: set[str] = set()
    for raw_capacity_class, raw_cp_capacity_kw, raw_share in capacity_mix:
        capacity_class = _require_non_empty_string(raw_capacity_class, "capacity_class")
        if capacity_class in seen_classes:
            raise ValueError("EV-008A capacity classes must be unique")
        seen_classes.add(capacity_class)
        cp_capacity_kw = _require_int(raw_cp_capacity_kw, f"{capacity_class} cp_capacity_kw")
        if cp_capacity_kw <= 0:
            raise ValueError("EV-008A cp_capacity_kw values must be positive")
        share = float(raw_share)
        if not np.isfinite(share) or share <= 0.0:
            raise ValueError("EV-008A capacity shares must be finite and positive")
        validated.append((capacity_class, cp_capacity_kw, share))
    return tuple(validated)


def _public_set_b_candidate_class_metadata(public_library: Mapping[str, Any]) -> dict[str, object]:
    batches = public_library.get("candidate_batches")
    if not isinstance(batches, (list, tuple)):
        raise ValueError("Public Set B library must include candidate_batches")
    by_class: dict[str, dict[str, object]] = {}
    expected_mix = {capacity_class: cp_capacity_kw for capacity_class, cp_capacity_kw, _ in EV_PUBLIC_SET_B_CAPACITY_MIX}
    for batch in batches:
        if not isinstance(batch, dict):
            raise ValueError("Public Set B candidate batches must be mappings")
        capacity_class = _require_non_empty_string(batch.get("capacity_class"), "capacity_class")
        cp_capacity_kw = _require_int(batch.get("cp_capacity_kw"), f"{capacity_class} cp_capacity_kw")
        if capacity_class not in expected_mix or expected_mix[capacity_class] != cp_capacity_kw:
            raise ValueError("Public Set B candidate batch does not match EV-008A capacity mix")
        n_profiles = _require_int(batch.get("n_profiles"), f"{capacity_class} n_profiles")
        if n_profiles != 100:
            raise ValueError("Public Set B candidate batches must contain 100 profiles")
        seed = _require_int(batch.get("seed"), f"{capacity_class} seed")
        processed_sha = _require_sha256(batch.get("processed_sha256_file"), "processed_sha256_file")
        record = by_class.setdefault(
            capacity_class,
            {
                "capacity_class": capacity_class,
                "cp_capacity_kw": cp_capacity_kw,
                "candidate_member_count": 0,
                "candidate_seeds": [],
                "processed_sha256_files": [],
            },
        )
        record["candidate_member_count"] = int(record["candidate_member_count"]) + n_profiles
        record["candidate_seeds"].append(seed)  # type: ignore[index]
        record["processed_sha256_files"].append(processed_sha)  # type: ignore[index]
    if set(by_class) != set(expected_mix):
        raise ValueError("Public Set B candidate library must cover all EV-008A capacity classes")
    for capacity_class, record in by_class.items():
        if record["candidate_member_count"] != 300:
            raise ValueError(f"Public Set B class {capacity_class} must have 300 candidate members")
        record["candidate_seeds"] = sorted(record["candidate_seeds"])  # type: ignore[index]
        record["processed_sha256_files"] = sorted(record["processed_sha256_files"])  # type: ignore[index]
    return {
        "candidate_member_count": public_library.get("candidate_member_count"),
        "candidate_batch_count": public_library.get("candidate_batch_count"),
        "capacity_classes": dict(sorted(by_class.items())),
        "member_reference": public_library.get("member_reference", {}),
    }

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


def _validate_local_count_workflow(workflow: Any, *, outlook_id: str) -> None:
    if not isinstance(workflow, dict):
        raise ValueError("local_count_workflow must be a mapping")
    if workflow.get("option") != "EV-007 Option A":
        raise ValueError("local_count_workflow must declare EV-007 Option A")
    status = str(workflow.get("status", ""))
    if status != "proposed_not_pi_signed":
        raise ValueError("local_count_workflow status must be proposed_not_pi_signed")
    area = workflow.get("selected_cluster")
    if not isinstance(area, dict):
        raise ValueError("local_count_workflow must include selected_cluster")
    if area.get("area_type") != "municipalities" or not area.get("area_identifier"):
        raise ValueError("EV-007 Option A cluster must declare a municipality area identifier")
    if area.get("selection_status") != "proposed_not_pi_signed":
        raise ValueError("Selected local cluster must remain proposed_not_pi_signed")
    records = workflow.get("proposed_2035_counts")
    if not isinstance(records, list) or not records:
        raise ValueError("local_count_workflow must include proposed_2035_counts")
    keys: set[tuple[int, str, str]] = set()
    for item in records:
        record = _proposed_local_count_from_mapping(
            item,
            outlook_id=outlook_id,
            workflow=workflow,
        )
        key = (record.year, record.scenario, record.location)
        if key in keys:
            raise ValueError("Proposed local count keys must be unique")
        keys.add(key)
    expected = {
        (2035, scenario, location)
        for scenario in {"low", "middle", "high"}
        for location in {"home", "public"}
    }
    if keys != expected:
        raise ValueError("Proposed local workflow must contain 2035 low/middle/high home and public counts")
    metadata = workflow.get("metadata")
    if not isinstance(metadata, dict) or not metadata.get("path") or not metadata.get("sha256"):
        raise ValueError("local_count_workflow must record metadata path and sha256")
    neighborhood = workflow.get("neighborhood_filter_attempt")
    if not isinstance(neighborhood, dict) or not neighborhood.get("query"):
        raise ValueError("local_count_workflow must record the neighbourhood-filter attempt")


def _proposed_local_count_from_mapping(
    item: Any,
    *,
    outlook_id: str,
    workflow: dict[str, Any],
) -> ProposedLocalChargePointCount:
    if not isinstance(item, dict):
        raise ValueError("Each proposed local count must be a mapping")
    status = str(item.get("status", ""))
    if status != "proposed_not_pi_signed":
        raise ValueError("Proposed local counts must remain proposed_not_pi_signed")
    year = _require_int(item.get("year"), "Proposed local count year")
    scenario = str(item.get("scenario", ""))
    location = str(item.get("location", ""))
    value = float(item.get("value", float("nan")))
    rounded_count = _require_int(item.get("rounded_count"), "Proposed local rounded_count")
    if year != 2035:
        raise ValueError("EV-007 local count proposal is limited to 2035 in this workflow")
    if scenario not in {"low", "middle", "high"}:
        raise ValueError("Proposed local scenario must be low, middle, or high")
    if location not in {"home", "public"}:
        raise ValueError("Proposed local location must be home or public")
    if not np.isfinite(value) or value < 0.0:
        raise ValueError("Proposed local value must be finite and non-negative")
    if rounded_count < 0 or rounded_count != int(round(value)):
        raise ValueError("Proposed local rounded_count must be the nearest integer API value")
    provenance = item.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("Proposed local counts must include provenance")
    if provenance.get("source_id") != outlook_id:
        raise ValueError("Proposed local counts must trace to the Outlook source ID")
    if provenance.get("source_type") != "local_outlook_cluster":
        raise ValueError("Proposed local counts must declare source_type=local_outlook_cluster")
    response_sha256 = str(provenance.get("response_sha256", ""))
    if len(response_sha256) != 64:
        raise ValueError("Proposed local counts must record a response sha256")
    query = str(provenance.get("query", ""))
    if "area_type=country" in query:
        raise ValueError("National Outlook projections cannot be used as proposed local counts")
    area = workflow["selected_cluster"]
    area_type = str(provenance.get("area_type", ""))
    area_identifier = str(provenance.get("area_identifier", ""))
    if area_type != area.get("area_type") or area_identifier != area.get("area_identifier"):
        raise ValueError("Proposed local count provenance must match the selected EV-007 cluster")
    return ProposedLocalChargePointCount(
        year=year,
        scenario=scenario,
        location=location,
        value=value,
        rounded_count=rounded_count,
        area_type=area_type,
        area_identifier=area_identifier,
        source_id=str(provenance["source_id"]),
        response_sha256=response_sha256,
        status=status,
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


def _validate_weight_pairs(weights: Sequence[tuple[str, float]]) -> None:
    allocate_charge_points_to_nodes(0, weights)


def _ev_profile_calendar_assumption() -> dict[str, int | str]:
    return {
        "source_calendar_local_year": 2025,
        "source_first_timestamp_utc": "2024-12-31T23:00:00+00:00",
        "source_first_timestamp_local": "2025-01-01T00:00:00+01:00",
        "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
        "step_seconds": 900,
        "timezone": LOCAL_TIMEZONE,
        "planning_year_use": "mapped_to_planning_year_calendar_before_ic1_aggregation",
    }


def _require_non_empty_string(value: Any, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{label} must be a non-empty string")
    return text


def _require_sha256(value: Any, label: str) -> str:
    text = _require_non_empty_string(value, label)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text.lower()):
        raise ValueError(f"{label} must be a sha256 hex digest")
    return text


def _require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be a true integer")
    return value


def _require_int_mapping(value: Any, label: str) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    result: dict[str, int] = {}
    for key, raw_count in value.items():
        node_id = _require_non_empty_string(key, f"{label} node_id")
        if node_id in result:
            raise ValueError(f"{label} must contain unique node IDs")
        count = _require_int(raw_count, f"{label}[{node_id}]")
        if count < 0:
            raise ValueError(f"{label} counts must be non-negative")
        result[node_id] = count
    if not result:
        raise ValueError(f"{label} must be non-empty")
    return result



def _validate_utc_time_axis(
    datetimes_utc: Sequence[datetime],
    expected_timesteps: int,
    *,
    label: str,
) -> None:
    if len(datetimes_utc) != expected_timesteps:
        raise ValueError(f"{label} must have {expected_timesteps} timestamps")
    for item in datetimes_utc:
        if item.tzinfo is None:
            raise ValueError(f"{label} timestamps must be timezone-aware")
    for previous, current in zip(datetimes_utc, datetimes_utc[1:]):
        if current.astimezone(UTC) - previous.astimezone(UTC) != timedelta(minutes=15):
            raise ValueError(f"{label} must have 900-second cadence")

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
