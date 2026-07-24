from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from src.rng import ComponentSelection, ComponentStream, SeedTree


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
            "G0-A3 approved threshold semantics must be implemented before event-based scientific analysis",
        ],
        "policy": {
            "candidate_libraries_only": True,
            "held_out_access": False,
            "profile_arrays_opened": False,
            "integrated_analysis_performed": False,
            "m_sufficiency_claimed": False,
        },
    }


def ev_candidate_profile_checksum_preflight_artifact(
    component_input_scaffold: Mapping[str, Any],
    readiness_record: Mapping[str, Any],
    checksum_verifications: Sequence[EVCandidateChecksumVerification],
    *,
    verification_timestamp_utc: str,
) -> dict[str, object]:
    """Record candidate processed-file checksum readiness before IC-1 array loading.

    This artifact is the last EV-side file-integrity gate before a future IC-1
    consumer may load generated candidate profile arrays from ignored local
    storage. It hashes file bytes only and deliberately keeps trajectory arrays
    unopened.
    """

    if component_input_scaffold.get("artifact_type") != "ev_ic1_component_input_scaffold":
        raise ValueError("Expected EV IC-1 component-input scaffold metadata")
    if component_input_scaffold.get("component_kind") != "ev":
        raise ValueError("EV checksum preflight requires an EV component scaffold")
    if component_input_scaffold.get("planning_year") != 2035:
        raise ValueError("EV checksum preflight currently targets planning year 2035")

    policy = component_input_scaffold.get("policy")
    if not isinstance(policy, dict):
        raise ValueError("EV component-input scaffold must include policy flags")
    required_false_flags = (
        "held_out_access",
        "quarantined_access",
        "profile_arrays_loaded",
        "integrated_analysis_performed",
        "event_or_p_e_analysis_performed",
        "capacity_screen_performed",
        "manuscript_numbers_produced",
        "m_sufficiency_claimed",
        "final_low_middle_high_branch_selected",
    )
    for flag in required_false_flags:
        if policy.get(flag) is not False:
            raise ValueError(f"EV checksum preflight requires scaffold policy {flag}=False")
    if policy.get("candidate_libraries_only") is not True:
        raise ValueError("EV checksum preflight requires candidate-only scaffold metadata")

    calendar = component_input_scaffold.get("calendar_mapping")
    if not isinstance(calendar, dict) or calendar.get("rule_id") != EV_CALENDAR_MAPPING_RULE_ID:
        raise ValueError("EV checksum preflight requires EV-CAL-001 calendar metadata")
    if calendar.get("n_timesteps") != EXPECTED_FULL_YEAR_STEPS:
        raise ValueError("EV checksum preflight requires complete annual EV profiles")

    expectations = ev_candidate_checksum_expectations(readiness_record)
    expected_by_key = {
        (item.component_id, item.library_id, item.seed): item for item in expectations
    }
    verified_by_key: dict[tuple[str, str, int], EVCandidateChecksumVerification] = {}
    for verification in checksum_verifications:
        key = (
            verification.expectation.component_id,
            verification.expectation.library_id,
            verification.expectation.seed,
        )
        if key not in expected_by_key:
            raise ValueError("EV checksum verification is not tied to a candidate expectation")
        verified_by_key[key] = verification
    if set(verified_by_key) != set(expected_by_key):
        raise ValueError("EV checksum preflight requires verification for every candidate batch")

    _require_non_empty_string(verification_timestamp_utc, "verification_timestamp_utc")
    verified_records = [
        verified_by_key[key].manifest_record() for key in sorted(verified_by_key)
    ]
    by_component: dict[str, dict[str, int]] = {}
    by_capacity_class: dict[str, int] = {}
    for record in verified_records:
        component_id = str(record["component_id"])
        component = by_component.setdefault(
            component_id, {"batch_count": 0, "member_count": 0, "byte_size": 0}
        )
        component["batch_count"] += 1
        component["member_count"] += _require_int(record.get("n_profiles"), "n_profiles")
        component["byte_size"] += _require_int(record.get("byte_size"), "byte_size")
        if component_id == EV_PUBLIC_COMPONENT:
            capacity_class = _require_non_empty_string(record.get("capacity_class"), "capacity_class")
            by_capacity_class[capacity_class] = by_capacity_class.get(capacity_class, 0) + _require_int(
                record.get("n_profiles"), "n_profiles"
            )

    source_artifacts = component_input_scaffold.get("source_artifacts")
    if not isinstance(source_artifacts, dict):
        raise ValueError("EV component-input scaffold must include source artifacts")

    return {
        "schema_version": 1,
        "artifact_type": "ev_ic1_candidate_profile_checksum_preflight",
        "artifact_id": "e2_s2_ev_candidate_profile_checksum_preflight",
        "status": "candidate_processed_checksums_verified_array_loading_still_blocked",
        "task_id": "E2.S2",
        "planning_year": 2035,
        "component_kind": "ev",
        "decision_ids": ["EV-003", "EV-005", "EV-005B", "EV-007A", "A-014", "EV-008A", "EV-CAL-001", "RNG-001"],
        "source_artifacts": {
            "component_input_scaffold": "data/metadata/ev_adoption/e2_s2_ev_ic1_component_input_scaffold.json",
            "candidate_adapter_artifact": source_artifacts.get("candidate_adapter_artifact"),
            "candidate_member_reference": source_artifacts.get("candidate_member_reference"),
            "candidate_selection_manifest_set": source_artifacts.get("candidate_selection_manifest_set"),
            "readiness_artifact": "data/metadata/ev_adoption/e2_s2_ev_integration_readiness.json",
        },
        "calendar_mapping": {
            "rule_id": EV_CALENDAR_MAPPING_RULE_ID,
            "rule_version": EV_CALENDAR_MAPPING_RULE_VERSION,
            "source_calendar_id": EV_SOURCE_CALENDAR_ID,
            "target_calendar_id": EV_TARGET_CALENDAR_ID,
            "source_timestep_i_maps_to_target_timestep_i": True,
            "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
            "weekday_mismatch_recorded_as_limitation": True,
        },
        "verification": {
            "timestamp_utc": verification_timestamp_utc,
            "method": "sha256_file_bytes_only_no_npz_array_loading",
            "candidate_batch_count": len(verified_records),
            "candidate_member_count": sum(_require_int(row.get("n_profiles"), "n_profiles") for row in verified_records),
            "candidate_processed_file_count": len(verified_records),
            "total_byte_size": sum(_require_int(row.get("byte_size"), "byte_size") for row in verified_records),
            "by_component": dict(sorted(by_component.items())),
            "public_member_count_by_capacity_class": dict(sorted(by_capacity_class.items())),
            "all_observed_sha256_match_expected": all(
                row.get("observed_sha256") == row.get("expected_sha256") for row in verified_records
            ),
            "verified_candidate_batches": verified_records,
        },
        "ic1_preconditions": {
            "candidate_processed_checksums_verified_in_agent_c_worktree": True,
            "future_consumer_must_reverify_ignored_files_before_array_loading": True,
            "candidate_selection_manifest_must_match_source_member_reference": True,
            "ev_cal001_mapping_required_before_common_calendar_consumption": True,
            "agent_a_ic1_consumption_not_performed_here": True,
        },
        "policy": {
            "candidate_libraries_only": True,
            "held_out_access": False,
            "quarantined_access": False,
            "profile_arrays_loaded": False,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
            "capacity_screen_performed": False,
            "final_low_middle_high_branch_selected": False,
            "m_sufficiency_claimed": False,
            "manuscript_numbers_produced": False,
        },
    }


def materialize_ev_ic1_candidate_component_outputs(
    component_input_scaffold: Mapping[str, Any],
    checksum_preflight_artifact: Mapping[str, Any],
    selection_manifest_set: Mapping[str, Any],
    *,
    base_dir: Path,
    output_dir: Path,
    materialized_timestamp_utc: str,
) -> dict[str, object]:
    """Materialize EV-only candidate component arrays for later IC-1 consumption.

    The materializer rehashes every candidate processed-profile file immediately
    before loading it. It only writes EV component outputs; net-load assembly,
    event detection, capacity screens, and library-adequacy claims stay outside
    this Agent C boundary.
    """

    if component_input_scaffold.get("artifact_type") != "ev_ic1_component_input_scaffold":
        raise ValueError("Expected EV IC-1 component-input scaffold metadata")
    if checksum_preflight_artifact.get("artifact_type") != "ev_ic1_candidate_profile_checksum_preflight":
        raise ValueError("Expected EV candidate profile checksum preflight metadata")
    if selection_manifest_set.get("artifact_type") != "ev_candidate_member_selection_manifest_set":
        raise ValueError("Expected EV-005B candidate member-selection manifest set")
    _require_non_empty_string(materialized_timestamp_utc, "materialized_timestamp_utc")

    scaffold_policy = component_input_scaffold.get("policy")
    checksum_policy = checksum_preflight_artifact.get("policy")
    selection_policy = selection_manifest_set.get("policy")
    for label, policy in (
        ("component-input scaffold", scaffold_policy),
        ("checksum preflight", checksum_policy),
        ("selection manifest", selection_policy),
    ):
        if not isinstance(policy, dict):
            raise ValueError(f"EV {label} must include policy flags")
        if policy.get("held_out_access") is not False:
            raise ValueError(f"EV {label} must block held-out access")
        if policy.get("quarantined_access") is not False:
            raise ValueError(f"EV {label} must block quarantined access")
        if policy.get("integrated_analysis_performed") is not False:
            raise ValueError(f"EV {label} must not include integrated analysis")
        if policy.get("m_sufficiency_claimed") is not False:
            raise ValueError(f"EV {label} must not claim M sufficiency")
    if selection_policy.get("candidate_only") is not True:
        raise ValueError("EV component outputs require candidate-only selections")
    if selection_policy.get("replacement_policy_id") != "EV-005B":
        raise ValueError("EV component outputs require EV-005B replacement provenance")

    calendar = component_input_scaffold.get("calendar_mapping")
    if not isinstance(calendar, dict) or calendar.get("rule_id") != EV_CALENDAR_MAPPING_RULE_ID:
        raise ValueError("EV component outputs require EV-CAL-001 calendar metadata")
    if calendar.get("n_timesteps") != EXPECTED_FULL_YEAR_STEPS:
        raise ValueError("EV component outputs require complete 35,040-step profiles")
    target_utc, _target_local = canonical_ev_planning_calendar_2035()
    timestamp_strings = np.array([item.isoformat() for item in target_utc])

    verification = checksum_preflight_artifact.get("verification")
    if not isinstance(verification, dict):
        raise ValueError("EV checksum preflight must include verification metadata")
    if verification.get("all_observed_sha256_match_expected") is not True:
        raise ValueError("EV checksum preflight must record matching candidate checksums")
    batch_records = verification.get("verified_candidate_batches")
    if not isinstance(batch_records, list) or not batch_records:
        raise ValueError("EV checksum preflight must list verified candidate batches")
    expected_sha_by_path: dict[str, str] = {}
    for record in batch_records:
        if not isinstance(record, dict):
            raise ValueError("EV checksum batch records must be mappings")
        processed_path = _require_non_empty_string(record.get("processed_path"), "processed_path")
        if "held_out" in processed_path or "quarantined" in processed_path:
            raise ValueError("EV component outputs may use candidate processed files only")
        expected_sha_by_path[processed_path] = _require_sha256(record.get("expected_sha256"), "expected_sha256")

    scenario_inputs = component_input_scaffold.get("scenario_inputs")
    if not isinstance(scenario_inputs, list) or not scenario_inputs:
        raise ValueError("EV component-input scaffold must include scenario inputs")
    scaffold_by_scenario = {
        _require_non_empty_string(row.get("scenario"), "scenario"): row
        for row in scenario_inputs
        if isinstance(row, dict)
    }
    selection_scenarios = selection_manifest_set.get("scenarios")
    if not isinstance(selection_scenarios, list) or not selection_scenarios:
        raise ValueError("EV selection manifest set must include scenarios")

    base_dir = Path(base_dir).resolve()
    output_dir = Path(output_dir)
    if not output_dir.is_absolute():
        output_dir = base_dir / output_dir
    output_dir = output_dir.resolve()
    try:
        output_dir.relative_to(base_dir)
    except ValueError as exc:
        raise ValueError("EV component output_dir must stay inside base_dir") from exc
    output_dir.mkdir(parents=True, exist_ok=True)
    loaded_batches: dict[str, ElaadProfileBatch] = {}
    reverified_files: dict[str, dict[str, object]] = {}

    def _load_reverified_batch(processed_path: str) -> ElaadProfileBatch:
        expected_sha = expected_sha_by_path.get(processed_path)
        if expected_sha is None:
            raise ValueError("selection references a processed path absent from checksum preflight")
        path = base_dir / Path(processed_path)
        observed_sha = _sha256_file(path)
        if observed_sha != expected_sha:
            raise ValueError(f"EV candidate checksum mismatch before array loading: {processed_path}")
        if processed_path not in loaded_batches:
            batch = load_processed_batch_npz(path)
            if batch.n_timesteps != EXPECTED_FULL_YEAR_STEPS:
                raise ValueError("EV candidate batches must contain complete annual profiles")
            loaded_batches[processed_path] = batch
            reverified_files[processed_path] = {
                "processed_path": processed_path,
                "sha256": observed_sha,
                "byte_size": path.stat().st_size,
                "n_profiles": batch.n_profiles,
                "n_timesteps": batch.n_timesteps,
            }
        return loaded_batches[processed_path]

    scenario_records: list[dict[str, object]] = []
    output_file_records: list[dict[str, object]] = []
    for scenario_record in sorted(selection_scenarios, key=lambda item: str(item.get("scenario", ""))):
        if not isinstance(scenario_record, dict):
            raise ValueError("EV selection scenario records must be mappings")
        scenario = _require_non_empty_string(scenario_record.get("scenario"), "scenario")
        scaffold = scaffold_by_scenario.get(scenario)
        if not isinstance(scaffold, dict):
            raise ValueError("EV component outputs require matching scaffold scenario inputs")
        node_inputs = scaffold.get("node_inputs")
        if not isinstance(node_inputs, list) or not node_inputs:
            raise ValueError("EV scaffold scenario must include node inputs")
        node_ids = tuple(_require_non_empty_string(row.get("node_id"), "node_id") for row in node_inputs if isinstance(row, dict))
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("EV component output node IDs must be unique")
        node_index_by_id = {node_id: index for index, node_id in enumerate(node_ids)}
        p_kw_by_node = np.zeros((len(node_ids), EXPECTED_FULL_YEAR_STEPS), dtype=np.float32)
        q_kvar_by_node = np.zeros_like(p_kw_by_node)
        selected_member_count = 0
        duplicate_selected_count = 0
        by_component: dict[str, int] = {EV_HOME_COMPONENT: 0, EV_PUBLIC_COMPONENT: 0}
        by_capacity_class: dict[str, int] = {}

        node_manifests = scenario_record.get("node_manifests")
        if not isinstance(node_manifests, list):
            raise ValueError("EV selection scenario must include node manifests")
        for node_manifest in node_manifests:
            if not isinstance(node_manifest, dict):
                raise ValueError("EV selection node manifests must be mappings")
            node_id = _require_non_empty_string(node_manifest.get("node_id"), "node_id")
            if node_id not in node_index_by_id:
                raise ValueError("EV selection node is absent from A-014 scaffold allocation")
            selections = node_manifest.get("selections")
            if not isinstance(selections, list):
                raise ValueError("EV selection node manifest must include selections")
            for selection in selections:
                if not isinstance(selection, dict):
                    raise ValueError("EV selection rows must be mappings")
                if selection.get("partition") != "candidate":
                    raise PermissionError("EV component outputs may only materialize candidate selections")
                component_id = _require_non_empty_string(selection.get("component_id"), "component_id")
                if component_id not in {EV_HOME_COMPONENT, EV_PUBLIC_COMPONENT}:
                    raise ValueError("EV selection component_id is unsupported")
                processed_path = _require_non_empty_string(selection.get("candidate_processed_path"), "candidate_processed_path")
                returned_index = _require_int(selection.get("returned_profile_index"), "returned_profile_index")
                batch = _load_reverified_batch(processed_path)
                if returned_index < 0 or returned_index >= batch.n_profiles:
                    raise ValueError("EV selection returned_profile_index is outside the candidate batch")
                source_member_id = _require_non_empty_string(selection.get("source_member_id"), "source_member_id")
                if batch.member_ids[returned_index] != source_member_id:
                    raise ValueError("EV selection source_member_id does not match the loaded candidate batch")
                p_kw_by_node[node_index_by_id[node_id], :] += batch.demands_kw[:, returned_index]
                selected_member_count += 1
                by_component[component_id] = by_component.get(component_id, 0) + 1
                if selection.get("duplicate_within_realization") is True:
                    duplicate_selected_count += 1
                if component_id == EV_PUBLIC_COMPONENT:
                    capacity_class = _require_non_empty_string(selection.get("capacity_class"), "capacity_class")
                    by_capacity_class[capacity_class] = by_capacity_class.get(capacity_class, 0) + 1

        output_path = output_dir / f"ev_ic1_candidate_component_output_{scenario}.npz"
        np.savez_compressed(
            output_path,
            p_kw_by_node=p_kw_by_node,
            q_kvar_by_node=q_kvar_by_node,
            timestamps_utc=timestamp_strings,
            node_ids=np.array(node_ids),
        )
        output_sha = _sha256_file(output_path)
        output_record = {
            "scenario": scenario,
            "path": output_path.relative_to(base_dir).as_posix(),
            "sha256": output_sha,
            "byte_size": output_path.stat().st_size,
            "node_count": len(node_ids),
            "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
            "array_shape": [len(node_ids), EXPECTED_FULL_YEAR_STEPS],
        }
        output_file_records.append(output_record)
        scenario_records.append(
            {
                "scenario": scenario,
                "planning_year": 2035,
                "node_count": len(node_ids),
                "selected_member_count": selected_member_count,
                "selected_member_count_by_component": dict(sorted(by_component.items())),
                "public_selected_member_count_by_capacity_class": dict(sorted(by_capacity_class.items())),
                "duplicate_selected_row_count": duplicate_selected_count,
                "component_streams": scenario_record.get("component_streams"),
                "output_file": output_record,
                "calendar_mapping_rule_id": EV_CALENDAR_MAPPING_RULE_ID,
                "total_conservation_verified_against_selection_manifest": True,
            }
        )

    return {
        "schema_version": 1,
        "artifact_type": "ev_ic1_candidate_component_output_manifest",
        "artifact_id": "e2_s2_ev_ic1_candidate_component_output_manifest",
        "status": "candidate_only_ev_component_outputs_materialized_for_ic1_preflight",
        "task_id": "E2.S2",
        "planning_year": 2035,
        "component_kind": "ev",
        "decision_ids": ["EV-003", "EV-005", "EV-005B", "EV-007A", "A-014", "EV-008A", "EV-CAL-001", "RNG-001"],
        "source_artifacts": {
            "component_input_scaffold": "data/metadata/ev_adoption/e2_s2_ev_ic1_component_input_scaffold.json",
            "checksum_preflight": "data/metadata/ev_adoption/e2_s2_ev_candidate_profile_checksum_preflight.json",
            "selection_manifest_set": "data/metadata/ev_adoption/e2_s2_ev005b_candidate_selection_manifests.json.gz",
        },
        "materialization": {
            "timestamp_utc": materialized_timestamp_utc,
            "method": "candidate_only_selection_sum_by_node_after_sha256_reverification",
            "candidate_files_reverified_before_array_loading": True,
            "candidate_processed_file_count": len(reverified_files),
            "loaded_candidate_profile_batches": len(loaded_batches),
            "output_directory": output_dir.relative_to(base_dir).as_posix(),
            "output_files": output_file_records,
            "reverified_candidate_files": [reverified_files[key] for key in sorted(reverified_files)],
        },
        "calendar_mapping": {
            "rule_id": EV_CALENDAR_MAPPING_RULE_ID,
            "rule_version": EV_CALENDAR_MAPPING_RULE_VERSION,
            "source_calendar_id": EV_SOURCE_CALENDAR_ID,
            "target_calendar_id": EV_TARGET_CALENDAR_ID,
            "source_timestep_i_maps_to_target_timestep_i": True,
            "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
            "weekday_mismatch_recorded_as_limitation": True,
        },
        "scenario_outputs": scenario_records,
        "ic1_boundary": {
            "component_adapter_output_ready_for_agent_a_preflight": True,
            "contains_ev_component_outputs_only": True,
            "agent_a_must_load_ignored_output_files_by_manifest_checksum": True,
            "not_a_net_load_result": True,
        },
        "policy": {
            "candidate_libraries_only": True,
            "held_out_access": False,
            "quarantined_access": False,
            "candidate_profile_arrays_loaded_for_ev_component_output_only": True,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
            "capacity_screen_performed": False,
            "final_low_middle_high_branch_selected": False,
            "m_sufficiency_claimed": False,
            "manuscript_numbers_produced": False,
        },
    }


def ev_ic1_component_output_consumption_packet(
    component_input_scaffold: Mapping[str, Any],
    component_output_manifest: Mapping[str, Any],
    *,
    component_output_manifest_sha256: str | None = None,
) -> dict[str, object]:
    """Build a fail-closed IC-1 consumption packet for EV component outputs.

    The packet is metadata only. It tells a future generic IC-1 loader exactly
    which ignored EV-only NPZ outputs may be consumed after checksum
    verification, without authorizing held-out access or downstream analysis.
    """

    if component_input_scaffold.get("artifact_type") != "ev_ic1_component_input_scaffold":
        raise ValueError("Expected EV IC-1 component-input scaffold metadata")
    if component_output_manifest.get("artifact_type") != "ev_ic1_candidate_component_output_manifest":
        raise ValueError("Expected EV IC-1 candidate component-output manifest")
    if component_input_scaffold.get("status") != "accepted_metadata_only_for_ic1_component_input_scaffold":
        raise ValueError("EV component-input scaffold must have accepted metadata-only status")
    if component_output_manifest.get("status") != "candidate_only_ev_component_outputs_materialized_for_ic1_preflight":
        raise ValueError("EV component-output manifest must have candidate-only preflight status")

    if component_output_manifest_sha256 is not None:
        component_output_manifest_sha256 = _require_sha256(
            component_output_manifest_sha256,
            "component_output_manifest_sha256",
        )

    scaffold_policy = component_input_scaffold.get("policy")
    output_policy = component_output_manifest.get("policy")
    for label, policy in (
        ("component-input scaffold", scaffold_policy),
        ("component-output manifest", output_policy),
    ):
        if not isinstance(policy, dict):
            raise ValueError(f"EV {label} must include policy flags")
        if policy.get("candidate_libraries_only") is not True:
            raise ValueError(f"EV {label} must be candidate-library only")
        if policy.get("held_out_access") is not False:
            raise ValueError(f"EV {label} must block held-out access")
        if policy.get("quarantined_access") is not False:
            raise ValueError(f"EV {label} must block quarantined access")
        if policy.get("integrated_analysis_performed") is not False:
            raise ValueError(f"EV {label} must not include integrated analysis")
        if policy.get("event_or_p_e_analysis_performed") is not False:
            raise ValueError(f"EV {label} must not include event or P(E) analysis")
        if policy.get("capacity_screen_performed") is not False:
            raise ValueError(f"EV {label} must not include capacity screens")
        if policy.get("m_sufficiency_claimed") is not False:
            raise ValueError(f"EV {label} must not claim EV library sufficiency")
        if policy.get("manuscript_numbers_produced") is not False:
            raise ValueError(f"EV {label} must not include manuscript numbers")
        if policy.get("final_low_middle_high_branch_selected") is not False:
            raise ValueError(f"EV {label} must not select a final scenario branch")

    if output_policy.get("candidate_profile_arrays_loaded_for_ev_component_output_only") is not True:
        raise ValueError("EV component-output manifest must identify EV-only candidate array materialization")

    required_decisions = ["EV-003", "EV-005", "EV-005B", "EV-007A", "A-014", "EV-008A", "EV-CAL-001", "RNG-001"]
    if component_output_manifest.get("decision_ids") != required_decisions:
        raise ValueError("EV component-output manifest decision IDs must match the approved candidate-only route")

    calendar = component_output_manifest.get("calendar_mapping")
    scaffold_calendar = component_input_scaffold.get("calendar_mapping")
    if not isinstance(calendar, dict) or not isinstance(scaffold_calendar, dict):
        raise ValueError("EV consumption packet requires calendar metadata")
    if calendar.get("rule_id") != EV_CALENDAR_MAPPING_RULE_ID or scaffold_calendar.get("rule_id") != EV_CALENDAR_MAPPING_RULE_ID:
        raise ValueError("EV consumption packet requires EV-CAL-001 calendar provenance")
    if calendar.get("n_timesteps") != EXPECTED_FULL_YEAR_STEPS or scaffold_calendar.get("n_timesteps") != EXPECTED_FULL_YEAR_STEPS:
        raise ValueError("EV consumption packet requires complete 35,040-step calendar metadata")

    adapter = component_input_scaffold.get("ic1_accepted_component_adapter_artifact")
    if not isinstance(adapter, dict):
        raise ValueError("EV component-input scaffold must include IC-1 adapter metadata")
    node_ids_raw = adapter.get("node_ids")
    if not isinstance(node_ids_raw, list):
        raise ValueError("EV IC-1 adapter metadata must include node_ids")
    node_ids = tuple(_require_non_empty_string(node_id, "node_id") for node_id in node_ids_raw)
    if len(node_ids) != 115 or len(set(node_ids)) != len(node_ids):
        raise ValueError("EV consumption packet requires 115 unique node IDs")
    if adapter.get("calendar_id") != EV_TARGET_CALENDAR_ID or adapter.get("timestep_seconds") != 900:
        raise ValueError("EV IC-1 adapter metadata must use the approved 2035 15-minute calendar")

    materialization = component_output_manifest.get("materialization")
    if not isinstance(materialization, dict):
        raise ValueError("EV component-output manifest must include materialization metadata")
    if materialization.get("candidate_files_reverified_before_array_loading") is not True:
        raise ValueError("EV component outputs must record candidate checksum reverification before array loading")
    output_files = materialization.get("output_files")
    scenario_outputs = component_output_manifest.get("scenario_outputs")
    scenario_inputs = component_input_scaffold.get("scenario_inputs")
    if not isinstance(output_files, list) or not isinstance(scenario_outputs, list) or not isinstance(scenario_inputs, list):
        raise ValueError("EV consumption packet requires scenario and output-file records")

    output_scenarios = [_require_non_empty_string(row.get("scenario"), "output scenario") for row in output_files if isinstance(row, dict)]
    scenario_output_names = [_require_non_empty_string(row.get("scenario"), "scenario output") for row in scenario_outputs if isinstance(row, dict)]
    scenario_input_names = [_require_non_empty_string(row.get("scenario"), "scenario input") for row in scenario_inputs if isinstance(row, dict)]
    for label, names in (
        ("output files", output_scenarios),
        ("scenario outputs", scenario_output_names),
        ("scenario inputs", scenario_input_names),
    ):
        duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
        if duplicates:
            raise ValueError(f"EV consumption packet rejects duplicate {label} scenarios: {duplicates}")
    scenario_set = set(scenario_input_names)
    if scenario_set != set(output_scenarios) or scenario_set != set(scenario_output_names):
        raise ValueError("EV consumption packet requires identical scenario coverage across inputs and outputs")
    if scenario_set != {"low", "middle", "high"}:
        raise ValueError("EV consumption packet expects the declared low/middle/high branches only")

    outputs_by_scenario = {row["scenario"]: row for row in output_files if isinstance(row, dict)}
    scenario_outputs_by_scenario = {row["scenario"]: row for row in scenario_outputs if isinstance(row, dict)}
    scenario_inputs_by_scenario = {row["scenario"]: row for row in scenario_inputs if isinstance(row, dict)}
    consumption_outputs: list[dict[str, object]] = []
    for scenario in sorted(scenario_set):
        output = outputs_by_scenario[scenario]
        scenario_output = scenario_outputs_by_scenario[scenario]
        scenario_input = scenario_inputs_by_scenario[scenario]
        output_file = scenario_output.get("output_file")
        if output_file != output:
            raise ValueError("EV scenario output_file records must match materialization output_files")
        path_value = _require_non_empty_string(output.get("path"), f"{scenario} output path")
        if not path_value.startswith("data/processed/elaad_profiles/component_outputs/") or "held_out" in path_value or "quarantined" in path_value:
            raise ValueError("EV consumption output paths must point to candidate component-output NPZs only")
        if _require_int(output.get("node_count"), f"{scenario} node_count") != len(node_ids):
            raise ValueError("EV consumption output node_count must match IC-1 node IDs")
        if _require_int(output.get("n_timesteps"), f"{scenario} n_timesteps") != EXPECTED_FULL_YEAR_STEPS:
            raise ValueError("EV consumption outputs must preserve 35,040 timesteps")
        if output.get("array_shape") != [len(node_ids), EXPECTED_FULL_YEAR_STEPS]:
            raise ValueError("EV consumption output array_shape must be node-major 115 x 35,040")
        if _require_int(output.get("byte_size"), f"{scenario} byte_size") <= 0:
            raise ValueError("EV consumption output byte_size must be positive")
        expected_component_counts = {
            EV_HOME_COMPONENT: scenario_input.get("home_charge_points"),
            EV_PUBLIC_COMPONENT: scenario_input.get("public_charge_points"),
        }
        if scenario_output.get("selected_member_count_by_component") != expected_component_counts:
            raise ValueError("EV consumption selected-member counts must match A-014 adoption totals")
        public_by_class = scenario_output.get("public_selected_member_count_by_capacity_class")
        if not isinstance(public_by_class, dict):
            raise ValueError("EV public selected member counts by capacity class must be recorded")
        consumption_outputs.append(
            {
                "scenario": scenario,
                "planning_year": _require_int(scenario_output.get("planning_year"), f"{scenario} planning_year"),
                "output_npz_path": path_value,
                "output_sha256": _require_sha256(output.get("sha256"), f"{scenario} output sha256"),
                "byte_size": _require_int(output.get("byte_size"), f"{scenario} byte_size"),
                "node_count": len(node_ids),
                "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
                "array_shape": [len(node_ids), EXPECTED_FULL_YEAR_STEPS],
                "home_charge_points": _require_int(scenario_input.get("home_charge_points"), f"{scenario} home_charge_points"),
                "public_charge_points": _require_int(scenario_input.get("public_charge_points"), f"{scenario} public_charge_points"),
                "selected_member_count_by_component": dict(sorted(scenario_output["selected_member_count_by_component"].items())),
                "duplicate_selected_row_count": _require_int(
                    scenario_output.get("duplicate_selected_row_count"),
                    f"{scenario} duplicate_selected_row_count",
                ),
                "public_selected_member_count_by_capacity_class": dict(sorted(public_by_class.items())),
            }
        )

    source_artifacts = component_input_scaffold.get("source_artifacts")
    if not isinstance(source_artifacts, dict):
        raise ValueError("EV component-input scaffold must include source artifacts")
    output_source_artifacts = component_output_manifest.get("source_artifacts")
    if not isinstance(output_source_artifacts, dict):
        raise ValueError("EV component-output manifest must include source artifacts")
    candidate_member_counts = component_input_scaffold.get("candidate_member_counts")
    if not isinstance(candidate_member_counts, dict):
        raise ValueError("EV component-input scaffold must include candidate member counts")
    selection_summary = component_input_scaffold.get("selection_manifest_summary")
    if not isinstance(selection_summary, dict):
        raise ValueError("EV component-input scaffold must include selection manifest summary")

    return {
        "schema_version": 1,
        "artifact_type": "ev_ic1_component_output_consumption_packet",
        "artifact_id": "e2_s2_ev_ic1_component_output_consumption_packet",
        "status": "candidate_only_component_outputs_ready_for_future_ic1_loader_preflight",
        "task_id": "E2.S2",
        "planning_year": 2035,
        "component_kind": "ev",
        "component_ids": [EV_HOME_COMPONENT, EV_PUBLIC_COMPONENT],
        "decision_ids": required_decisions,
        "source_ids": ["D-002", "D-010", "D-012"],
        "source_artifacts": {
            "component_input_scaffold": "data/metadata/ev_adoption/e2_s2_ev_ic1_component_input_scaffold.json",
            "component_output_manifest": "data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_component_output_manifest.json",
            "component_output_manifest_sha256": component_output_manifest_sha256,
            "candidate_adapter_artifact": source_artifacts.get("candidate_adapter_artifact"),
            "candidate_member_reference": source_artifacts.get("candidate_member_reference"),
            "candidate_selection_manifest_set": source_artifacts.get("candidate_selection_manifest_set"),
            "candidate_selection_manifest_set_sha256": source_artifacts.get("candidate_selection_manifest_set_sha256"),
            "checksum_preflight": output_source_artifacts.get("checksum_preflight"),
        },
        "allowed_consumer": {
            "agent_a_generic_loader_may_consume_after_sha256_verification": True,
            "agent_a_must_verify_each_output_npz_sha256_before_loading": True,
            "agent_a_must_keep_scenario_branch_explicit": True,
            "ic1_preflight_or_real_artifact_assembly_only": True,
            "paper_facing_integrated_adequacy_use_allowed": False,
        },
        "required_status_fields": {
            "component_input_scaffold.status": "accepted_metadata_only_for_ic1_component_input_scaffold",
            "component_output_manifest.status": "candidate_only_ev_component_outputs_materialized_for_ic1_preflight",
            "component_output_manifest.ic1_boundary.component_adapter_output_ready_for_agent_a_preflight": True,
            "component_output_manifest.ic1_boundary.contains_ev_component_outputs_only": True,
            "component_output_manifest.ic1_boundary.not_a_net_load_result": True,
        },
        "calendar_mapping": {
            "rule_id": EV_CALENDAR_MAPPING_RULE_ID,
            "rule_version": EV_CALENDAR_MAPPING_RULE_VERSION,
            "source_calendar_id": EV_SOURCE_CALENDAR_ID,
            "target_calendar_id": EV_TARGET_CALENDAR_ID,
            "source_timestep_i_maps_to_target_timestep_i": True,
            "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
            "timestep_seconds": 900,
            "weekday_mismatch_recorded_as_limitation": True,
        },
        "node_axis": {
            "node_ids": list(node_ids),
            "node_count": len(node_ids),
            "node_axis_index_order": "matches_npz_node_ids_array_and_this_packet",
        },
        "source_profile_libraries": {
            EV_HOME_COMPONENT: {
                "library_id": "A_home_vancar_cp_y2030",
                "candidate_member_count": 1000,
                "source_id": "D-002",
                "profile_type": "cp",
                "location_type": "home",
                "simulated_year": 2030,
                "cp_capacity_kw": 11,
            },
            EV_PUBLIC_COMPONENT: {
                "library_id": EV_PUBLIC_SET_B_LIBRARY_ID,
                "candidate_member_count": 1200,
                "source_id": "D-002",
                "context_source_id": "D-012",
                "profile_type": "cp",
                "location_type": "public",
                "simulated_year": 2030,
                "capacity_class_member_counts": candidate_member_counts.get("public_by_capacity_class"),
            },
        },
        "a014_allocation_provenance": {
            "decision_id": "A-014",
            "local_count_decision_id": "EV-007A",
            "allocation_rule": "static_p_mw_weights_largest_remainder",
            "scenario_input_pointer": "data/metadata/ev_adoption/e2_s2_ev_ic1_component_input_scaffold.json#/scenario_inputs",
            "final_low_middle_high_branch_selected": False,
        },
        "selection_manifest_provenance": {
            "decision_id": "EV-005B",
            "selection_manifest_set_path": source_artifacts.get("candidate_selection_manifest_set"),
            "selection_manifest_set_sha256": source_artifacts.get("candidate_selection_manifest_set_sha256"),
            "root_seed": selection_summary.get("root_seed"),
            "sample_index": selection_summary.get("sample_index"),
            "duplicate_summary": selection_summary.get("duplicate_summary"),
            "replacement": "with_replacement_charge_point_level_candidate_only",
        },
        "component_output_contract": {
            "file_format": "npz",
            "arrays": {
                "p_kw_by_node": {"shape": ["node", "timestep"], "unit": "kW"},
                "q_kvar_by_node": {"shape": ["node", "timestep"], "unit": "kvar"},
                "timestamps_utc": {"length": EXPECTED_FULL_YEAR_STEPS, "timezone": "UTC"},
                "node_ids": {"length": len(node_ids), "order": "row order for p_kw_by_node/q_kvar_by_node"},
            },
            "scenario_outputs": consumption_outputs,
        },
        "policy": {
            "candidate_libraries_only": True,
            "held_out_access": False,
            "quarantined_access": False,
            "profile_arrays_loaded_in_this_packet": False,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
            "capacity_screen_performed": False,
            "final_low_middle_high_branch_selected": False,
            "m_sufficiency_claimed": False,
            "manuscript_numbers_produced": False,
        },
    }


def ev_ic1_accepted_artifact_index_preflight(
    consumption_packet: Mapping[str, Any],
    adoption_artifact: Mapping[str, Any],
    *,
    consumption_packet_path: str = "data/metadata/ev_adoption/e2_s2_ev_ic1_component_output_consumption_packet.json",
    consumption_packet_sha256: str | None = None,
    adoption_artifact_path: str = "data/metadata/ev_adoption/e2_s6_a014_alkmaar_executable_adoption_artifact.json",
    adoption_artifact_sha256: str | None = None,
) -> dict[str, object]:
    """Index accepted EV metadata artifacts for a future IC-1 preflight.

    The index is a metadata-only acceptance surface. It joins the candidate EV
    component-output packet to the accepted A-014 adoption artifact, but keeps
    scientific-result use blocked until downstream adequacy and scenario gates
    pass.
    """

    if consumption_packet.get("artifact_type") != "ev_ic1_component_output_consumption_packet":
        raise ValueError("EV accepted-artifact index requires the EV component-output consumption packet")
    if adoption_artifact.get("artifact_type") != "a014_executable_ev_adoption_allocation_artifact":
        raise ValueError("EV accepted-artifact index requires the A-014 executable adoption artifact")
    if consumption_packet.get("status") != "candidate_only_component_outputs_ready_for_future_ic1_loader_preflight":
        raise ValueError("EV component-output packet must be accepted for candidate-only loader preflight")
    if adoption_artifact.get("status") != "accepted_executable_per_node_ev_adoption_allocation":
        raise ValueError("A-014 adoption artifact must be accepted executable allocation metadata")

    if consumption_packet_sha256 is not None:
        consumption_packet_sha256 = _require_sha256(consumption_packet_sha256, "consumption_packet_sha256")
    if adoption_artifact_sha256 is not None:
        adoption_artifact_sha256 = _require_sha256(adoption_artifact_sha256, "adoption_artifact_sha256")

    required_consumption_decisions = [
        "EV-003",
        "EV-005",
        "EV-005B",
        "EV-007A",
        "A-014",
        "EV-008A",
        "EV-CAL-001",
        "RNG-001",
    ]
    if consumption_packet.get("decision_ids") != required_consumption_decisions:
        raise ValueError("EV consumption packet decision IDs do not match the accepted EV IC-1 route")
    if adoption_artifact.get("decision_ids") != ["EV-007", "EV-007A", "A-014"]:
        raise ValueError("A-014 adoption artifact decision IDs do not match the accepted adoption route")

    for label, policy in (
        ("consumption packet", consumption_packet.get("policy")),
        ("adoption artifact", adoption_artifact.get("policy")),
    ):
        if not isinstance(policy, dict):
            raise ValueError(f"EV {label} must include policy flags")
        if policy.get("held_out_access") is not False:
            raise ValueError(f"EV {label} must block held-out access")
        if policy.get("quarantined_access") is not False:
            raise ValueError(f"EV {label} must block quarantined access")
        if policy.get("integrated_analysis_performed") is not False:
            raise ValueError(f"EV {label} must not include integrated analysis")
        if policy.get("event_or_p_e_analysis_performed") is not False:
            raise ValueError(f"EV {label} must not include event or P(E) analysis")
        if policy.get("capacity_screen_performed") is not False:
            raise ValueError(f"EV {label} must not include capacity screens")
        if policy.get("m_sufficiency_claimed") is not False:
            raise ValueError(f"EV {label} must not claim EV library sufficiency")
        if policy.get("manuscript_numbers_produced") is not False:
            raise ValueError(f"EV {label} must not include manuscript numbers")
        if policy.get("final_low_middle_high_branch_selected") is not False:
            raise ValueError(f"EV {label} must not select the final low/middle/high branch")
    if consumption_packet["policy"].get("candidate_libraries_only") is not True:
        raise ValueError("EV consumption packet must be candidate-library only")
    if adoption_artifact["policy"].get("executable_adoption_counts") is not True:
        raise ValueError("A-014 adoption artifact must expose executable adoption counts")
    if adoption_artifact["policy"].get("candidate_profile_arrays_loaded") is not False:
        raise ValueError("A-014 adoption artifact must not load EV profile arrays")

    allowed_consumer = consumption_packet.get("allowed_consumer")
    if not isinstance(allowed_consumer, dict):
        raise ValueError("EV consumption packet must include allowed_consumer flags")
    if allowed_consumer.get("agent_a_generic_loader_may_consume_after_sha256_verification") is not True:
        raise ValueError("EV consumption packet must allow only checksum-verified generic loading")
    if allowed_consumer.get("agent_a_must_keep_scenario_branch_explicit") is not True:
        raise ValueError("EV consumption packet must require explicit scenario branches")
    if allowed_consumer.get("paper_facing_integrated_adequacy_use_allowed") is not False:
        raise ValueError("EV consumption packet must block paper-facing integrated adequacy use")

    if _require_int(consumption_packet.get("planning_year"), "consumption planning_year") != 2035:
        raise ValueError("EV accepted-artifact index requires planning year 2035")
    if _require_int(adoption_artifact.get("planning_year"), "adoption planning_year") != 2035:
        raise ValueError("A-014 accepted-artifact index requires planning year 2035")

    calendar = consumption_packet.get("calendar_mapping")
    if not isinstance(calendar, dict):
        raise ValueError("EV consumption packet must include calendar mapping")
    if calendar.get("rule_id") != EV_CALENDAR_MAPPING_RULE_ID:
        raise ValueError("EV accepted-artifact index requires EV-CAL-001 calendar mapping")
    if calendar.get("source_timestep_i_maps_to_target_timestep_i") is not True:
        raise ValueError("EV calendar mapping must use ordinal timestep mapping")
    if _require_int(calendar.get("n_timesteps"), "calendar n_timesteps") != EXPECTED_FULL_YEAR_STEPS:
        raise ValueError("EV accepted-artifact index requires complete 35,040-step calendar")
    if _require_int(calendar.get("timestep_seconds"), "calendar timestep_seconds") != 900:
        raise ValueError("EV accepted-artifact index requires 15-minute cadence")

    consumption_node_axis = consumption_packet.get("node_axis")
    adoption_node_axis = adoption_artifact.get("node_axis")
    if not isinstance(consumption_node_axis, dict) or not isinstance(adoption_node_axis, dict):
        raise ValueError("EV accepted-artifact index requires node-axis metadata")
    consumption_nodes = tuple(
        _require_non_empty_string(node_id, "EV consumption node_id")
        for node_id in consumption_node_axis.get("node_ids", [])
    )
    adoption_nodes = tuple(
        _require_non_empty_string(node_id, "A-014 adoption node_id")
        for node_id in adoption_node_axis.get("node_ids", [])
    )
    if len(consumption_nodes) != 115 or len(set(consumption_nodes)) != len(consumption_nodes):
        raise ValueError("EV consumption packet must expose 115 unique node IDs")
    if consumption_nodes != adoption_nodes:
        raise ValueError("EV consumption and A-014 adoption node axes must match exactly")

    contract = consumption_packet.get("component_output_contract")
    if not isinstance(contract, dict):
        raise ValueError("EV consumption packet must include component output contract")
    output_records = contract.get("scenario_outputs")
    adoption_records = adoption_artifact.get("scenario_allocations")
    if not isinstance(output_records, list) or not isinstance(adoption_records, list):
        raise ValueError("EV accepted-artifact index requires scenario records")
    output_scenarios = [_require_non_empty_string(row.get("scenario"), "output scenario") for row in output_records if isinstance(row, dict)]
    adoption_scenarios_seen = [_require_non_empty_string(row.get("scenario"), "adoption scenario") for row in adoption_records if isinstance(row, dict)]
    for label, names in (("output", output_scenarios), ("adoption", adoption_scenarios_seen)):
        duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
        if duplicates:
            raise ValueError(f"EV accepted-artifact index rejects duplicate {label} scenarios: {duplicates}")
    scenario_set = set(output_scenarios)
    if scenario_set != {"low", "middle", "high"} or scenario_set != set(adoption_scenarios_seen):
        raise ValueError("EV accepted-artifact index requires identical low/middle/high scenario coverage")

    adoption_by_scenario = {row["scenario"]: row for row in adoption_records if isinstance(row, dict)}
    output_by_scenario = {row["scenario"]: row for row in output_records if isinstance(row, dict)}
    scenario_index: list[dict[str, object]] = []
    for scenario in sorted(scenario_set):
        output = output_by_scenario[scenario]
        adoption = adoption_by_scenario[scenario]
        if _require_int(output.get("node_count"), f"{scenario} output node_count") != 115:
            raise ValueError("EV component-output node counts must match A-014 node axis")
        if _require_int(adoption.get("node_count"), f"{scenario} adoption node_count") != 115:
            raise ValueError("A-014 adoption node counts must match EV node axis")
        home_total = _require_int(adoption.get("home_charge_points"), f"{scenario} adoption home")
        public_total = _require_int(adoption.get("public_charge_points"), f"{scenario} adoption public")
        if _require_int(output.get("home_charge_points"), f"{scenario} output home") != home_total:
            raise ValueError("EV output home count must match A-014 adoption total")
        if _require_int(output.get("public_charge_points"), f"{scenario} output public") != public_total:
            raise ValueError("EV output public count must match A-014 adoption total")
        if adoption.get("total_conservation_verified") is not True:
            raise ValueError("A-014 scenario allocations must verify total conservation")
        if adoption.get("nonnegative_integer_counts_verified") is not True:
            raise ValueError("A-014 scenario allocations must verify nonnegative integer counts")
        node_allocations = adoption.get("node_allocations")
        if not isinstance(node_allocations, list) or len(node_allocations) != 115:
            raise ValueError("A-014 scenario allocations must expose 115 node rows")
        if {row.get("node_id") for row in node_allocations if isinstance(row, dict)} != set(consumption_nodes):
            raise ValueError("A-014 scenario node rows must match EV consumption node IDs")
        capacity_counts = output.get("public_selected_member_count_by_capacity_class")
        if not isinstance(capacity_counts, dict) or set(capacity_counts) != {"public_11kw", "public_13kw", "public_15kw", "public_22kw"}:
            raise ValueError("EV public outputs must expose all EV-008A capacity classes")
        if sum(_require_int(value, f"{scenario} capacity count") for value in capacity_counts.values()) != public_total:
            raise ValueError("EV public capacity-class counts must conserve the public adoption total")
        scenario_index.append(
            {
                "scenario": scenario,
                "planning_year": 2035,
                "scenario_branch_must_be_explicit": True,
                "final_paper_branch_selected": False,
                "output_npz_path": _require_non_empty_string(output.get("output_npz_path"), f"{scenario} output path"),
                "output_sha256": _require_sha256(output.get("output_sha256"), f"{scenario} output_sha256"),
                "node_count": 115,
                "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
                "home_charge_points": home_total,
                "public_charge_points": public_total,
                "public_capacity_class_counts": dict(sorted(capacity_counts.items())),
                "duplicate_selected_row_count": _require_int(
                    output.get("duplicate_selected_row_count"),
                    f"{scenario} duplicate_selected_row_count",
                ),
                "a014_node_allocation_pointer": (
                    "data/metadata/ev_adoption/e2_s6_a014_alkmaar_executable_adoption_artifact.json"
                    f"#/scenario_allocations/{scenario}"
                ),
            }
        )

    consumption_sources = consumption_packet.get("source_artifacts")
    adoption_sources = adoption_artifact.get("source_artifacts")
    if not isinstance(consumption_sources, dict) or not isinstance(adoption_sources, dict):
        raise ValueError("EV accepted-artifact index requires source artifact metadata")
    for key in (
        "component_output_manifest_sha256",
        "candidate_selection_manifest_set_sha256",
    ):
        _require_sha256(consumption_sources.get(key), key)
    for key in ("scenario_config_sha256", "historical_preview_artifact_sha256"):
        _require_sha256(adoption_sources.get(key), key)

    remaining_blockers = [
        {
            "blocker_id": "E3.S2a-EV-HELD-OUT-ADEQUACY-NOT-RUN",
            "status": "blocked",
            "reason": "Held-out and quarantined EV batches remain closed until the downstream criterion is frozen and invoked.",
        },
        {
            "blocker_id": "EV-005-M-SUFFICIENCY-NOT-CERTIFIED",
            "status": "blocked",
            "reason": "Candidate M=1000 home and M=1200 public are usable source libraries, not adequacy certifications.",
        },
        {
            "blocker_id": "G5-FINAL-LOW-MIDDLE-HIGH-BRANCH-NOT-SELECTED",
            "status": "blocked",
            "reason": "EV-007A declares all three 2035 branches; no final paper branch has been chosen.",
        },
        {
            "blocker_id": "IC-1-INTEGRATED-NET-LOAD-ASSEMBLY-NOT-RUN",
            "status": "blocked",
            "reason": "This index covers EV component metadata only and is not a net-load, event, or P(E) result.",
        },
        {
            "blocker_id": "A-016-CROSS-COMPONENT-SCENARIO-CONSISTENCY-NOT-YET-CHECKED",
            "status": "blocked",
            "reason": "EV, HP, PV, and baseline source-lineage consistency must be checked before integrated analysis.",
        },
    ]

    return {
        "schema_version": 1,
        "artifact_type": "ev_ic1_accepted_artifact_index_preflight",
        "artifact_id": "e2_s2_ev_ic1_accepted_artifact_index_preflight",
        "status": "accepted_ev_metadata_index_for_agent_a_preflight_blocked_for_integrated_results",
        "task_id": "E2.S2/E2.S6",
        "component_kind": "ev",
        "planning_year": 2035,
        "decision_ids": sorted(set(required_consumption_decisions + ["EV-007"])),
        "source_ids": ["D-002", "D-010", "D-012"],
        "source_artifacts": {
            "component_output_consumption_packet": consumption_packet_path,
            "component_output_consumption_packet_sha256": consumption_packet_sha256,
            "a014_executable_adoption_artifact": adoption_artifact_path,
            "a014_executable_adoption_artifact_sha256": adoption_artifact_sha256,
            "component_output_manifest": consumption_sources.get("component_output_manifest"),
            "component_output_manifest_sha256": consumption_sources.get("component_output_manifest_sha256"),
            "candidate_member_reference": consumption_sources.get("candidate_member_reference"),
            "candidate_selection_manifest_set": consumption_sources.get("candidate_selection_manifest_set"),
            "candidate_selection_manifest_set_sha256": consumption_sources.get("candidate_selection_manifest_set_sha256"),
            "checksum_preflight": consumption_sources.get("checksum_preflight"),
            "scenario_config": adoption_sources.get("scenario_config"),
            "scenario_config_sha256": adoption_sources.get("scenario_config_sha256"),
            "local_count_metadata": adoption_sources.get("local_count_metadata"),
        },
        "accepted_for_agent_a_preflight": {
            "metadata_index_may_be_consumed": True,
            "agent_a_must_verify_this_index_sha256": True,
            "agent_a_must_verify_source_artifact_sha256s": True,
            "agent_a_must_verify_each_output_npz_sha256_before_loading": True,
            "scenario_branch_must_be_explicit": True,
            "reject_unknown_scenario_branch": True,
            "paper_facing_integrated_use_allowed": False,
        },
        "calendar_mapping": {
            "rule_id": EV_CALENDAR_MAPPING_RULE_ID,
            "rule_version": EV_CALENDAR_MAPPING_RULE_VERSION,
            "source_calendar_id": EV_SOURCE_CALENDAR_ID,
            "target_calendar_id": EV_TARGET_CALENDAR_ID,
            "source_timestep_i_maps_to_target_timestep_i": True,
            "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
            "timestep_seconds": 900,
            "weekday_mismatch_recorded_as_limitation": True,
        },
        "node_axis": {
            "node_ids": list(consumption_nodes),
            "node_count": len(consumption_nodes),
            "node_axis_order": consumption_node_axis.get("node_axis_index_order", adoption_node_axis.get("node_axis_order")),
            "a014_node_axis_order": adoption_node_axis.get("node_axis_order"),
        },
        "scenario_index": scenario_index,
        "source_profile_libraries": consumption_packet.get("source_profile_libraries"),
        "a014_allocation_provenance": {
            "decision_id": "A-014",
            "local_count_decision_id": "EV-007A",
            "adoption_artifact_status": adoption_artifact.get("status"),
            "allocation_method": adoption_artifact.get("allocation_method"),
            "selected_local_proxy": adoption_artifact.get("selected_local_proxy"),
            "scenario_selection": adoption_artifact.get("scenario_selection"),
        },
        "selection_manifest_provenance": consumption_packet.get("selection_manifest_provenance"),
        "component_output_contract": {
            "file_format": contract.get("file_format"),
            "arrays": contract.get("arrays"),
            "scenario_outputs_pointer": (
                "data/metadata/ev_adoption/e2_s2_ev_ic1_component_output_consumption_packet.json"
                "#/component_output_contract/scenario_outputs"
            ),
        },
        "remaining_blockers": remaining_blockers,
        "policy": {
            "candidate_libraries_only": True,
            "held_out_access": False,
            "quarantined_access": False,
            "profile_arrays_loaded_in_this_index": False,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
            "capacity_screen_performed": False,
            "final_low_middle_high_branch_selected": False,
            "m_sufficiency_claimed": False,
            "manuscript_numbers_produced": False,
            "fail_closed_on_unresolved_blockers": True,
        },
    }


EV_GENERIC_COMPONENT_OUTPUT_MANIFEST_DIR = "data/metadata/ev_adoption/generic_component_output_manifests"
EV_GENERIC_COMPONENT_OUTPUT_PACKET_PATH = (
    "data/metadata/ev_adoption/e3_s2a_ev_ic1_generic_component_output_manifest_packet.json"
)
EV_MULTI_NODE_OUTPUT_CONTRACT_BLOCKER_ID = "A-LOADER-MULTI-NODE-EV-OUTPUT-CONTRACT-NOT-YET-SIGNED"
EV_MULTI_NODE_OUTPUT_NODE_ID = "ev_multi_node_axis_115"


def ev_ic1_generic_component_output_loader_manifests(
    accepted_artifact_index: Mapping[str, Any],
    recovery_preflight: Mapping[str, Any],
    *,
    accepted_artifact_index_path: str = "data/metadata/ev_adoption/e2_s2_ev_ic1_accepted_artifact_index_preflight.json",
    accepted_artifact_index_sha256: str | None = None,
    recovery_preflight_path: str = "data/metadata/ev_adoption/e3_s2a_ev_component_output_recovery_preflight.json",
    recovery_preflight_sha256: str | None = None,
    manifest_directory: str = EV_GENERIC_COMPONENT_OUTPUT_MANIFEST_DIR,
    manifest_sha256_by_path: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Build Agent A-loader-compatible EV component-output manifests.

    The returned wrapper is metadata-only. It translates the richer EV
    candidate-output index into the generic IC-1 manifest keys that Agent A's
    loader preflight validates, while preserving EV fail-closed blockers in
    provenance instead of authorizing adequacy or integrated use.
    """

    if accepted_artifact_index.get("artifact_type") != "ev_ic1_accepted_artifact_index_preflight":
        raise ValueError("generic EV loader manifests require the EV accepted-artifact index")
    if accepted_artifact_index.get("status") != "accepted_ev_metadata_index_for_agent_a_preflight_blocked_for_integrated_results":
        raise ValueError("generic EV loader manifests require the accepted EV metadata index")
    if recovery_preflight.get("artifact_type") != "ev_component_output_recovery_preflight":
        raise ValueError("generic EV loader manifests require the EV component-output recovery preflight")
    if recovery_preflight.get("status") != "component_outputs_rebuilt_and_verified":
        raise ValueError("generic EV loader manifests require verified rebuilt component outputs")

    if accepted_artifact_index_sha256 is not None:
        accepted_artifact_index_sha256 = _require_sha256(
            accepted_artifact_index_sha256,
            "accepted_artifact_index_sha256",
        )
    if recovery_preflight_sha256 is not None:
        recovery_preflight_sha256 = _require_sha256(
            recovery_preflight_sha256,
            "recovery_preflight_sha256",
        )

    for label, policy in (
        ("accepted artifact index", accepted_artifact_index.get("policy")),
        ("recovery preflight", recovery_preflight.get("policy")),
    ):
        if not isinstance(policy, Mapping):
            raise ValueError(f"EV {label} must include policy flags")
        for key in (
            "held_out_access",
            "quarantined_access",
            "integrated_analysis_performed",
        ):
            if policy.get(key) is not False:
                raise ValueError(f"EV {label} must keep {key}=False")
        if policy.get("m_sufficiency_claim") is True or policy.get("m_sufficiency_claimed") is True:
            raise ValueError(f"EV {label} must not claim M sufficiency")
    if accepted_artifact_index["policy"].get("candidate_libraries_only") is not True:
        raise ValueError("generic EV loader manifests require candidate-library-only EV metadata")
    if recovery_preflight["policy"].get("elaad_api_calls") is not False:
        raise ValueError("generic EV loader manifests must not depend on new ElaadNL API calls")
    if recovery_preflight["policy"].get("profile_arrays_loaded_during_candidate_restore") is not False:
        raise ValueError("generic EV loader manifests require restore-only recovery metadata")
    source_root = recovery_preflight.get("candidate_source_root")
    if not isinstance(source_root, Mapping) or source_root.get("absolute_path_committed") is not False:
        raise ValueError("generic EV loader manifests must not commit absolute candidate-source roots")

    scenario_index = accepted_artifact_index.get("scenario_index")
    if not isinstance(scenario_index, list):
        raise ValueError("generic EV loader manifests require a scenario index")
    scenario_names = [_require_non_empty_string(row.get("scenario"), "scenario") for row in scenario_index if isinstance(row, Mapping)]
    duplicates = sorted(name for name, count in Counter(scenario_names).items() if count > 1)
    if duplicates:
        raise ValueError(f"generic EV loader manifests reject duplicate scenarios: {duplicates}")
    if set(scenario_names) != {"low", "middle", "high"}:
        raise ValueError("generic EV loader manifests require low/middle/high scenario coverage")

    rebuilt_records = recovery_preflight.get("rebuilt_component_outputs")
    if not isinstance(rebuilt_records, list):
        raise ValueError("generic EV loader manifests require rebuilt component-output records")
    rebuilt_by_scenario: dict[str, Mapping[str, Any]] = {}
    for record in rebuilt_records:
        if not isinstance(record, Mapping):
            raise ValueError("rebuilt component-output records must be mappings")
        scenario = _require_non_empty_string(record.get("scenario"), "rebuilt scenario")
        if scenario in rebuilt_by_scenario:
            raise ValueError(f"generic EV loader manifests reject duplicate rebuilt scenario: {scenario}")
        rebuilt_by_scenario[scenario] = record
    if set(rebuilt_by_scenario) != set(scenario_names):
        raise ValueError("generic EV loader manifests require rebuilt outputs for every declared scenario")

    calendar = accepted_artifact_index.get("calendar_mapping")
    node_axis = accepted_artifact_index.get("node_axis")
    source_artifacts = accepted_artifact_index.get("source_artifacts")
    if not isinstance(calendar, Mapping) or not isinstance(node_axis, Mapping) or not isinstance(source_artifacts, Mapping):
        raise ValueError("generic EV loader manifests require calendar, node-axis, and source-artifact metadata")
    if calendar.get("rule_id") != EV_CALENDAR_MAPPING_RULE_ID:
        raise ValueError("generic EV loader manifests require EV-CAL-001 calendar mapping")
    if _require_int(calendar.get("n_timesteps"), "calendar n_timesteps") != EXPECTED_FULL_YEAR_STEPS:
        raise ValueError("generic EV loader manifests require 35,040 timesteps")
    if _require_int(calendar.get("timestep_seconds"), "calendar timestep_seconds") != 900:
        raise ValueError("generic EV loader manifests require 900-second cadence")
    if node_axis.get("node_count") != 115:
        raise ValueError("generic EV loader manifests require the 115-node EV axis")

    manifest_dir = _require_non_empty_string(manifest_directory, "manifest_directory").rstrip("/")
    manifest_sha256_by_path = dict(manifest_sha256_by_path or {})
    manifests: list[dict[str, object]] = []
    scenario_manifest_records: list[dict[str, object]] = []
    for row in sorted((r for r in scenario_index if isinstance(r, Mapping)), key=lambda item: str(item["scenario"])):
        scenario = str(row["scenario"])
        rebuilt = rebuilt_by_scenario[scenario]
        output_path = _require_non_empty_string(row.get("output_npz_path"), f"{scenario} output_npz_path")
        output_sha = _require_sha256(row.get("output_sha256"), f"{scenario} output_sha256")
        if rebuilt.get("path") != output_path or rebuilt.get("sha256") != output_sha:
            raise ValueError("generic EV loader manifests require recovery output checksums to match the accepted index")
        manifest_path = f"{manifest_dir}/ev_2035_{scenario}.json"
        member_id = f"ev005b_root20260722_sample0_{scenario}_branch"
        manifest = {
            "artifact_id": f"e3_s2a_ev_ic1_generic_component_output_2035_{scenario}",
            "artifact_status": "blocked_multi_node_contract",
            "kind": "ev",
            "component_id": f"ev_component_output_2035_{scenario}",
            "node_id": EV_MULTI_NODE_OUTPUT_NODE_ID,
            "member_id": member_id,
            "source_id": "D-002_D-010_D-012",
            "calendar_id": calendar.get("target_calendar_id"),
            "timestep_seconds": 900,
            "array_path": output_path,
            "array_sha256": output_sha,
            "provenance": {
                "artifact_type": "ev_generic_ic1_component_output_manifest",
                "scenario": scenario,
                "planning_year": 2035,
                "candidate_only": True,
                "held_out_access": False,
                "quarantined_access": False,
                "m_sufficiency_claimed": False,
                "integrated_analysis_performed": False,
                "event_or_p_e_analysis_performed": False,
                "capacity_screen_performed": False,
                "final_low_middle_high_branch_selected": False,
                "profile_arrays_loaded_by_manifest_builder": False,
                "agent_a_schema_target": "build_accepted_artifact_loader_blocker_preflight",
                "agent_a_loader_boundary": {
                    "ready_for_current_npz_loader": False,
                    "blocker_id": EV_MULTI_NODE_OUTPUT_CONTRACT_BLOCKER_ID,
                    "reason": (
                        "EV currently stores one 115-node component-output NPZ per scenario, while the "
                        "current Agent A NPZ artifact loader expects a one-node one-dimensional payload."
                    ),
                    "required_resolution": (
                        "Agent A signs a multi-node component-output loader contract or Agent C exports "
                        "per-node EV manifests before real IC-1 loading."
                    ),
                },
                "multi_node_axis_note": (
                    "The node_id field is a non-loadable axis marker for schema-shaped metadata only; "
                    "the EV NPZ carries the full 115-row node axis recorded here."
                ),
                "node_axis": node_axis,
                "calendar_mapping": calendar,
                "scenario_index_record": dict(row),
                "source_profile_libraries": accepted_artifact_index.get("source_profile_libraries"),
                "a014_allocation_provenance": accepted_artifact_index.get("a014_allocation_provenance"),
                "selection_manifest_provenance": accepted_artifact_index.get("selection_manifest_provenance"),
                "source_artifacts": {
                    **dict(source_artifacts),
                    "accepted_artifact_index": accepted_artifact_index_path,
                    "accepted_artifact_index_sha256": accepted_artifact_index_sha256,
                    "component_output_recovery_preflight": recovery_preflight_path,
                    "component_output_recovery_preflight_sha256": recovery_preflight_sha256,
                },
                "remaining_blockers": accepted_artifact_index.get("remaining_blockers"),
            },
        }
        manifests.append(manifest)
        scenario_manifest_records.append(
            {
                "scenario": scenario,
                "path": manifest_path,
                "sha256": manifest_sha256_by_path.get(manifest_path),
                "array_path": output_path,
                "array_sha256": output_sha,
                "agent_a_loader_inputs": {
                    "component_output_manifest_paths_by_kind": {"ev": manifest_path},
                    "component_output_manifest_sha256_by_path": (
                        {manifest_path: manifest_sha256_by_path[manifest_path]}
                        if manifest_path in manifest_sha256_by_path
                        else {}
                    ),
                },
            }
        )

    missing_manifest_sha = [record["path"] for record in scenario_manifest_records if not record.get("sha256")]
    multi_node_contract_blocker = {
        "blocker_id": EV_MULTI_NODE_OUTPUT_CONTRACT_BLOCKER_ID,
        "status": "blocked",
        "reason": (
            "EV component-output NPZs are multi-node arrays over 115 SimBench load nodes, but the current "
            "Agent A accepted NPZ artifact loader expects one-dimensional p_kw/q_kvar/timestamps for one node."
        ),
        "required_resolution": (
            "Use an A-owned multi-node component-output loader or an EV-owned per-node manifest/export strategy "
            "before real IC-1 loading."
        ),
    }
    remaining_blockers = list(accepted_artifact_index.get("remaining_blockers") or [])
    if not any(row.get("blocker_id") == EV_MULTI_NODE_OUTPUT_CONTRACT_BLOCKER_ID for row in remaining_blockers if isinstance(row, Mapping)):
        remaining_blockers.append(multi_node_contract_blocker)

    return {
        "artifact_type": "ev_ic1_generic_component_output_manifest_packet",
        "artifact_id": "e3_s2a_ev_ic1_generic_component_output_manifest_packet",
        "schema_version": 1,
        "task_id": "E3.S2a",
        "status": "blocked_ev_generic_loader_manifests_multi_node_contract",
        "component_kind": "ev",
        "planning_year": 2035,
        "decision_ids": accepted_artifact_index.get("decision_ids"),
        "source_ids": accepted_artifact_index.get("source_ids"),
        "generic_loader_schema": {
            "compatible_with": "build_accepted_artifact_loader_blocker_preflight_schema_keys_only",
            "ready_for_current_agent_a_npz_loader": False,
            "blocker_id": EV_MULTI_NODE_OUTPUT_CONTRACT_BLOCKER_ID,
            "required_keys_present_in_each_manifest": [
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
            ],
            "scenario_branch_must_be_explicit": True,
        },
        "scenario_manifests": scenario_manifest_records,
        "manifests_by_scenario": {record["scenario"]: manifest for record, manifest in zip(scenario_manifest_records, manifests, strict=True)},
        "source_artifacts": {
            "accepted_artifact_index": accepted_artifact_index_path,
            "accepted_artifact_index_sha256": accepted_artifact_index_sha256,
            "component_output_recovery_preflight": recovery_preflight_path,
            "component_output_recovery_preflight_sha256": recovery_preflight_sha256,
        },
        "loader_contract_blocker": multi_node_contract_blocker,
        "remaining_blockers": remaining_blockers,
        "missing_generic_manifest_sha256_paths": missing_manifest_sha,
        "policy": {
            "candidate_libraries_only": True,
            "held_out_access": False,
            "quarantined_access": False,
            "profile_arrays_loaded_by_manifest_builder": False,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
            "capacity_screen_performed": False,
            "final_low_middle_high_branch_selected": False,
            "m_sufficiency_claimed": False,
            "manuscript_numbers_produced": False,
            "fail_closed_on_unresolved_blockers": True,
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
            "replacement_policy_id": "EV-005B",
            "replacement_rule_chosen": True,
            "replacement_policy_scope": "candidate_member_selection_only",
            "component_stream_required": True,
            "sample_rows_materialized_in_reference": False,
            "candidate_selection_manifest_set": "data/metadata/ev_adoption/e2_s2_ev005b_candidate_selection_manifests.json.gz",
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


def e3_s2a_ev_heldout_adequacy_preflight_blockers(
    accepted_artifact_index: Mapping[str, Any],
    criterion_packet: Mapping[str, Any],
    *,
    accepted_artifact_index_path: str = "data/metadata/ev_adoption/e2_s2_ev_ic1_accepted_artifact_index_preflight.json",
    accepted_artifact_index_sha256: str | None = None,
    criterion_packet_path: str = "data/metadata/ev_adoption/e3_s2a_ev_adequacy_criterion_packet.json",
    criterion_packet_sha256: str | None = None,
    candidate_output_checksum_verification: Mapping[str, Any] | None = None,
    candidate_output_checksum_verification_path: str | None = None,
    candidate_output_checksum_verification_sha256: str | None = None,
    ic1_assembly_status: str = "not_accepted",
    held_out_access_status: str = "not_invoked",
    scenario_consistency_status: str = "not_resolved",
    final_scenario_branch: str | None = None,
    local_candidate_output_checksums_verified: bool = False,
) -> dict[str, object]:
    """Build the fail-closed E3.S2a EV held-out adequacy preflight manifest.

    The preflight intentionally reports blockers instead of running adequacy.
    It validates candidate-side metadata and criterion status, but never opens
    held-out/quarantined paths or loads generated profile arrays.
    """

    if accepted_artifact_index.get("artifact_type") != "ev_ic1_accepted_artifact_index_preflight":
        raise ValueError("E3.S2a EV preflight requires the accepted EV IC-1 artifact index")
    if accepted_artifact_index.get("status") != "accepted_ev_metadata_index_for_agent_a_preflight_blocked_for_integrated_results":
        raise ValueError("EV accepted-artifact index must retain fail-closed preflight status")
    if criterion_packet.get("artifact_type") != "ev_downstream_adequacy_criterion_packet":
        raise ValueError("E3.S2a EV preflight requires the downstream adequacy criterion packet")
    if criterion_packet.get("task_id") != "E3.S2a":
        raise ValueError("EV adequacy criterion packet must belong to E3.S2a")

    if accepted_artifact_index_sha256 is not None:
        accepted_artifact_index_sha256 = _require_sha256(
            accepted_artifact_index_sha256,
            "accepted_artifact_index_sha256",
        )
    if criterion_packet_sha256 is not None:
        criterion_packet_sha256 = _require_sha256(criterion_packet_sha256, "criterion_packet_sha256")
    if candidate_output_checksum_verification_sha256 is not None:
        candidate_output_checksum_verification_sha256 = _require_sha256(
            candidate_output_checksum_verification_sha256,
            "candidate_output_checksum_verification_sha256",
        )

    policy = accepted_artifact_index.get("policy")
    if not isinstance(policy, dict):
        raise ValueError("EV accepted-artifact index must include policy flags")
    for key in (
        "held_out_access",
        "quarantined_access",
        "integrated_analysis_performed",
        "event_or_p_e_analysis_performed",
        "capacity_screen_performed",
        "final_low_middle_high_branch_selected",
        "m_sufficiency_claimed",
        "manuscript_numbers_produced",
    ):
        if policy.get(key) is not False:
            raise ValueError(f"EV accepted-artifact index must keep {key}=False")
    if policy.get("candidate_libraries_only") is not True:
        raise ValueError("EV accepted-artifact index must remain candidate-library only")
    if policy.get("fail_closed_on_unresolved_blockers") is not True:
        raise ValueError("EV accepted-artifact index must fail closed on unresolved blockers")

    non_claims = criterion_packet.get("non_claims")
    if not isinstance(non_claims, dict):
        raise ValueError("EV adequacy criterion packet must include non_claims")
    for key in (
        "held_out_access",
        "profile_arrays_loaded",
        "integrated_analysis_performed",
        "event_or_p_e_analysis_performed",
        "m_sufficiency_claimed",
        "manuscript_numbers_produced",
    ):
        if non_claims.get(key) is not False:
            raise ValueError(f"EV adequacy criterion packet must keep {key}=False")

    scenario_index = accepted_artifact_index.get("scenario_index")
    if not isinstance(scenario_index, list):
        raise ValueError("EV accepted-artifact index must include scenario_index")
    scenario_names = [_require_non_empty_string(row.get("scenario"), "scenario") for row in scenario_index if isinstance(row, dict)]
    duplicates = sorted(name for name, count in Counter(scenario_names).items() if count > 1)
    if duplicates:
        raise ValueError(f"E3.S2a EV preflight rejects duplicate scenario index rows: {duplicates}")
    if set(scenario_names) != {"low", "middle", "high"}:
        raise ValueError("E3.S2a EV preflight requires low/middle/high scenario index coverage")

    missing_inputs: list[dict[str, object]] = []
    for label, path_value, sha_value in (
        ("accepted_artifact_index", accepted_artifact_index_path, accepted_artifact_index_sha256),
        ("criterion_packet", criterion_packet_path, criterion_packet_sha256),
    ):
        if not path_value:
            missing_inputs.append({"input": label, "missing": "path"})
        if sha_value is None:
            missing_inputs.append({"input": label, "missing": "sha256"})
    source_artifacts = accepted_artifact_index.get("source_artifacts")
    if not isinstance(source_artifacts, dict):
        raise ValueError("EV accepted-artifact index must include source_artifacts")
    for key in (
        "component_output_manifest",
        "component_output_manifest_sha256",
        "candidate_member_reference",
        "candidate_selection_manifest_set",
        "candidate_selection_manifest_set_sha256",
        "checksum_preflight",
        "scenario_config",
        "scenario_config_sha256",
        "local_count_metadata",
    ):
        value = source_artifacts.get(key)
        if value in (None, ""):
            missing_inputs.append({"input": f"source_artifacts.{key}", "missing": "value"})
    for key in (
        "component_output_manifest_sha256",
        "candidate_selection_manifest_set_sha256",
        "scenario_config_sha256",
    ):
        if source_artifacts.get(key) not in (None, ""):
            _require_sha256(source_artifacts.get(key), key)

    checksum_verification_status = "not_run"
    checksum_verification_records_by_scenario: dict[str, Mapping[str, Any]] = {}
    checksum_verification_missing: list[object] = []
    checksum_verification_mismatches: list[object] = []
    if candidate_output_checksum_verification is not None:
        if candidate_output_checksum_verification.get("artifact_type") != "ev_candidate_component_output_checksum_verification":
            raise ValueError("EV candidate output checksum verification artifact has unexpected type")
        verification_policy = candidate_output_checksum_verification.get("policy")
        if not isinstance(verification_policy, dict):
            raise ValueError("EV candidate output checksum verification must include policy")
        for key in (
            "held_out_access",
            "quarantined_access",
            "profile_arrays_loaded",
            "integrated_analysis_performed",
            "event_or_p_e_analysis_performed",
            "capacity_screen_performed",
            "m_sufficiency_claimed",
            "manuscript_numbers_produced",
        ):
            if verification_policy.get(key) is not False:
                raise ValueError(f"EV candidate output checksum verification must keep {key}=False")
        if verification_policy.get("hash_file_bytes_only") is not True:
            raise ValueError("EV candidate output checksum verification must hash file bytes only")
        checksum_verification_status = _require_non_empty_string(
            candidate_output_checksum_verification.get("status"),
            "candidate output checksum verification status",
        )
        checksum_records = candidate_output_checksum_verification.get("verification_records")
        if not isinstance(checksum_records, list):
            raise ValueError("EV candidate output checksum verification must include verification_records")
        names = [_require_non_empty_string(record.get("scenario"), "checksum scenario") for record in checksum_records if isinstance(record, dict)]
        duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
        if duplicates:
            raise ValueError(f"EV candidate output checksum verification rejects duplicate scenarios: {duplicates}")
        if set(names) != set(scenario_names):
            raise ValueError("EV candidate output checksum verification must cover the accepted scenario set")
        checksum_verification_records_by_scenario = {
            _require_non_empty_string(record.get("scenario"), "checksum scenario"): record
            for record in checksum_records
            if isinstance(record, dict)
        }
        checksum_verification_missing = list(candidate_output_checksum_verification.get("missing_outputs", []))
        checksum_verification_mismatches = list(candidate_output_checksum_verification.get("checksum_mismatches", []))
        local_candidate_output_checksums_verified = (
            candidate_output_checksum_verification.get("all_expected_outputs_verified") is True
        )

    output_checksum_records: list[dict[str, object]] = []
    for row in scenario_index:
        if not isinstance(row, dict):
            raise ValueError("EV scenario_index rows must be mappings")
        scenario = _require_non_empty_string(row.get("scenario"), "scenario")
        output_path = _require_non_empty_string(row.get("output_npz_path"), f"{scenario} output_npz_path")
        output_sha = _require_sha256(row.get("output_sha256"), f"{scenario} output_sha256")
        if "held_out" in output_path or "quarantined" in output_path:
            raise ValueError("EV E3.S2a preflight candidate output paths must not reference held-out/quarantined data")
        verification_record = checksum_verification_records_by_scenario.get(scenario)
        if verification_record is not None:
            if verification_record.get("output_npz_path") != output_path:
                raise ValueError("EV candidate output checksum verification path must match accepted index")
            if verification_record.get("expected_sha256") != output_sha:
                raise ValueError("EV candidate output checksum verification digest must match accepted index")
        output_checksum_records.append(
            {
                "scenario": scenario,
                "output_npz_path": output_path,
                "expected_sha256": output_sha,
                "local_checksum_verified_in_this_preflight": bool(local_candidate_output_checksums_verified),
                "verification_status": (
                    None if verification_record is None else verification_record.get("status")
                ),
                "observed_sha256": (
                    None if verification_record is None else verification_record.get("observed_sha256")
                ),
                "byte_size": None if verification_record is None else verification_record.get("byte_size"),
            }
        )

    blocker_rows: list[dict[str, object]] = []

    def add_blocker(blocker_id: str, reason: str, *, source: str, resolution: str) -> None:
        blocker_rows.append(
            {
                "blocker_id": blocker_id,
                "source": source,
                "status": "blocked",
                "reason": reason,
                "resolution_required": resolution,
            }
        )

    if criterion_packet.get("status") != "approved_signed_downstream_adequacy_criterion":
        add_blocker(
            "E3.S2A-DOWNSTREAM-AGGREGATE-ADEQUACY-CRITERION-NOT-SIGNED",
            "The criterion packet is still unsigned and PI decision values/tolerances are not available.",
            source="e3_s2a_ev_adequacy_criterion_packet",
            resolution="PI signs the downstream integrated criterion and all numerical tolerance fields before any held-out result is inspected.",
        )
    if ic1_assembly_status != "accepted":
        add_blocker(
            "E3.S2-IC1-ASSEMBLY-NOT-ACCEPTED",
            "Agent A IC-1 assembly is not accepted as the downstream aggregation surface for adequacy.",
            source="ic1_assembly_status",
            resolution="Agent A delivers and PI accepts the IC-1 assembly path for baseline, EV, HP, PV, adoption, and flexibility on one common calendar.",
        )
    if held_out_access_status != "explicitly_invoked_after_signed_criterion":
        add_blocker(
            "EV-HELD-OUT-ACCESS-NOT-EXPLICITLY-INVOKED",
            "Held-out access remains closed in this scaffold and has not been explicitly invoked after criterion approval.",
            source="held_out_access_status",
            resolution="Invoke held-out access only in a later manifest after E3.S2a criterion approval and IC-1 readiness.",
        )
    if scenario_consistency_status != "resolved":
        add_blocker(
            "A-016-SCENARIO-CONSISTENCY-NOT-RESOLVED",
            "Cross-component 2035 source/scenario consistency has not been resolved for EV, HP, PV, and baseline.",
            source="A-016",
            resolution="Record the A-016 scenario-consistency manifest before integrated adequacy runs.",
        )
    if final_scenario_branch not in {"low", "middle", "high"}:
        add_blocker(
            "G5-FINAL-LOW-MIDDLE-HIGH-BRANCH-NOT-SELECTED",
            "The final 2035 low/middle/high paper branch has not been selected.",
            source="G5",
            resolution="Select an approved final branch through the signed G5 route; until then, any adequacy design must keep branches explicit.",
        )
    if not local_candidate_output_checksums_verified:
        reason = "The ignored candidate EV component-output NPZ files were not checksummed in this preflight worktree."
        if checksum_verification_missing:
            reason = "Candidate EV component-output checksum verification ran and found missing ignored NPZ files."
        elif checksum_verification_mismatches:
            reason = "Candidate EV component-output checksum verification ran and found checksum mismatches."
        add_blocker(
            "EV-CANDIDATE-OUTPUT-CHECKSUMS-NOT-VERIFIED-IN-CONSUMING-WORKTREE",
            reason,
            source="candidate_output_manifest",
            resolution="Before executable adequacy, verify each candidate output NPZ against the accepted artifact index in the consuming worktree.",
        )
    if missing_inputs:
        add_blocker(
            "E3.S2A-MISSING-CHECKSUM-OR-MANIFEST-INPUT",
            "One or more required metadata paths/checksums are missing from the preflight inputs.",
            source="preflight_input_validation",
            resolution="Restore the missing committed manifest path or SHA-256 provenance before invoking adequacy.",
        )

    for inherited in accepted_artifact_index.get("remaining_blockers", []):
        if not isinstance(inherited, dict):
            continue
        inherited_id = _require_non_empty_string(inherited.get("blocker_id"), "inherited blocker_id")
        if inherited_id in {row["blocker_id"] for row in blocker_rows}:
            continue
        add_blocker(
            inherited_id,
            _require_non_empty_string(inherited.get("reason"), "inherited blocker reason"),
            source="ev_ic1_accepted_artifact_index_preflight",
            resolution="Resolve the inherited EV accepted-artifact-index blocker before E3.S2a execution.",
        )

    blocker_rows = sorted(blocker_rows, key=lambda row: str(row["blocker_id"]))
    return {
        "schema_version": 1,
        "artifact_type": "e3_s2a_ev_heldout_adequacy_preflight_blocker_manifest",
        "artifact_id": "e3_s2a_ev_heldout_adequacy_preflight_blockers",
        "task_id": "E3.S2a",
        "status": "blocked_before_held_out_access",
        "purpose": (
            "Automate EV-side held-out adequacy preflight checks and emit blockers without opening "
            "held-out/quarantined batches or producing integrated results."
        ),
        "source_artifacts": {
            "accepted_artifact_index": accepted_artifact_index_path,
            "accepted_artifact_index_sha256": accepted_artifact_index_sha256,
            "criterion_packet": criterion_packet_path,
            "criterion_packet_sha256": criterion_packet_sha256,
            "candidate_output_checksum_verification": candidate_output_checksum_verification_path,
            "candidate_output_checksum_verification_sha256": candidate_output_checksum_verification_sha256,
            "component_output_manifest": source_artifacts.get("component_output_manifest"),
            "component_output_manifest_sha256": source_artifacts.get("component_output_manifest_sha256"),
            "candidate_selection_manifest_set": source_artifacts.get("candidate_selection_manifest_set"),
            "candidate_selection_manifest_set_sha256": source_artifacts.get("candidate_selection_manifest_set_sha256"),
            "checksum_preflight": source_artifacts.get("checksum_preflight"),
            "scenario_config": source_artifacts.get("scenario_config"),
            "scenario_config_sha256": source_artifacts.get("scenario_config_sha256"),
        },
        "governing_decisions": sorted(
            set(
                list(accepted_artifact_index.get("decision_ids", []))
                + list(criterion_packet.get("governing_decisions", []))
                + ["A-016", "ALEA-002"]
            )
        ),
        "scenario_scope": {
            "planning_year": _require_int(accepted_artifact_index.get("planning_year"), "planning_year"),
            "declared_branches": sorted(scenario_names),
            "final_scenario_branch": final_scenario_branch,
            "final_branch_selected": final_scenario_branch in {"low", "middle", "high"},
        },
        "candidate_output_checksum_inputs": sorted(output_checksum_records, key=lambda row: str(row["scenario"])),
        "candidate_output_checksum_verification": {
            "status": checksum_verification_status,
            "artifact_path": candidate_output_checksum_verification_path,
            "artifact_sha256": candidate_output_checksum_verification_sha256,
            "all_expected_outputs_verified": bool(local_candidate_output_checksums_verified),
            "missing_output_count": len(checksum_verification_missing),
            "checksum_mismatch_count": len(checksum_verification_mismatches),
            "checkpointed_script": "data/get_ev_adequacy_preflight.py --verify-candidate-output-checksums",
            "resume_procedure": (
                "Restore the missing ignored EV component-output NPZ files, then rerun "
                "./.venv/Scripts/python.exe data/get_ev_adequacy_preflight.py --verify-candidate-output-checksums"
            ),
        },
        "missing_checksum_or_manifest_inputs": missing_inputs,
        "later_runner_scaffold": {
            "candidate_vs_held_out_comparison_planned": True,
            "compare_after_ic1_net_load_aggregation_only": True,
            "event_metric_requires_signed_criterion": True,
            "runner_manifest_required_for_any_result": True,
            "held_out_access_default": False,
            "quarantined_access_default": False,
            "component_only_adequacy_disallowed": True,
            "alpha_indexed_bounds_required": True,
        },
        "blockers": blocker_rows,
        "blocked": bool(blocker_rows),
        "policy": {
            "held_out_access": False,
            "quarantined_access": False,
            "profile_arrays_loaded": False,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
            "capacity_screen_performed": False,
            "m_sufficiency_claimed": False,
            "manuscript_numbers_produced": False,
            "fail_closed_on_blockers": True,
        },
    }


def ev005_within_realization_replacement_policy_packet() -> dict[str, object]:
    """Return the EV-005B replacement-policy decision packet."""

    return {
        "schema_version": 1,
        "artifact_type": "ev005_within_realization_replacement_policy_packet",
        "decision_id": "EV-005B",
        "task_id": "E2.S2",
        "status": "approved_for_candidate_member_selection_only",
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
                "status": "approved_ev005b_policy",
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
                "pi_approval": "Approved in chat on 2026-07-22 for candidate member-selection implementation only",
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
            "selection manifests record scenario, node_id, component_id, capacity_class, selection_index, source_member_id, library_id, batch_seed, returned_profile_index, processed checksum, stream_id, replacement flag, and multiplicity",
        ],
        "non_claims": {
            "policy_signed": True,
            "held_out_access": False,
            "profile_arrays_loaded": False,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
            "m_sufficiency_claimed": False,
            "manuscript_numbers_produced": False,
        },
    }


def ev_candidate_member_selection_manifest(
    candidate_member_reference: Mapping[str, Any],
    *,
    decisions_text: str,
    scenario: str,
    node_id: str,
    component_id: str,
    required_members: int,
    component_stream: ComponentStream,
    capacity_class: str | None = None,
    cp_capacity_kw: int | None = None,
    planning_year: int = 2035,
) -> dict[str, object]:
    """Select candidate EV source members only after EV-005B approval.

    This function intentionally works from committed member metadata rather than
    profile arrays; generated NPZ loading remains a later IC-1 consumption step.
    """

    members = _validated_candidate_member_rows(candidate_member_reference)
    scenario_name = _require_non_empty_string(scenario, "scenario")
    node_name = _require_non_empty_string(node_id, "node_id")
    component_name = _require_non_empty_string(component_id, "component_id")
    if component_name not in {EV_HOME_COMPONENT, EV_PUBLIC_COMPONENT}:
        raise ValueError("EV member selection requires a supported EV component_id")
    if component_stream.component != component_name:
        raise ValueError("EV member selection requires the matching RNG-001 component stream")
    requested = _require_int(required_members, "required_members")
    if requested < 0:
        raise ValueError("required_members must be non-negative")
    if component_name == EV_PUBLIC_COMPONENT:
        capacity_name = _require_non_empty_string(capacity_class, "capacity_class")
        capacity_kw = _require_int(cp_capacity_kw, "cp_capacity_kw")
    else:
        capacity_name = None
        capacity_kw = None if cp_capacity_kw is None else _require_int(cp_capacity_kw, "cp_capacity_kw")
    pool = [
        row
        for row in members
        if row["component_id"] == component_name
        and (capacity_name is None or row.get("capacity_class") == capacity_name)
    ]
    if not pool and requested:
        raise ValueError("No candidate EV source members match the requested component/capacity class")

    _require_ev005b_approved(decisions_text)
    if requested == 0:
        selected_indices: list[int] = []
    else:
        rng = component_stream.rng()
        selected_indices = [int(index) for index in rng.choice(len(pool), size=requested, replace=True)]
    selected_pairs = [(pool_index, pool[pool_index]) for pool_index in selected_indices]
    multiplicities = Counter(str(row["source_member_id"]) for _pool_index, row in selected_pairs)
    positions: dict[str, list[int]] = {}
    for selection_index, (_pool_index, row) in enumerate(selected_pairs):
        positions.setdefault(str(row["source_member_id"]), []).append(selection_index)

    selections: list[dict[str, object]] = []
    for selection_index, (pool_index, row) in enumerate(selected_pairs):
        member_id = str(row["source_member_id"])
        multiplicity = int(multiplicities[member_id])
        selections.append(
            {
                "scenario": scenario_name,
                "planning_year": planning_year,
                "sample_index": component_stream.sample_index,
                "component_id": component_name,
                "component_stream_id": component_stream.stream_id,
                "component_seed": component_stream.seed,
                "node_id": node_name,
                "capacity_class": capacity_name,
                "cp_capacity_kw": capacity_kw,
                "selection_index": selection_index,
                "selection_pool_index": pool_index,
                "selection_count_at_node": requested,
                "replacement_policy_id": "EV-005B",
                "replacement_enabled": True,
                "source_member_id": member_id,
                "library_id": str(row["library_id"]),
                "partition": str(row["partition"]),
                "control_mode": str(row["control_mode"]),
                "batch_seed": int(row["batch_seed"]),
                "returned_profile_index": int(row["returned_profile_index"]),
                "candidate_processed_path": str(row["processed_path"]),
                "candidate_processed_sha256_file": str(row["candidate_processed_sha256_file"]),
                "calendar_mapping_rule_id": str(row["calendar_mapping_rule_id"]),
                "calendar_mapping_rule_version": str(row["calendar_mapping_rule_version"]),
                "source_calendar_id": str(row["source_calendar_id"]),
                "target_calendar_id": str(row["target_calendar_id"]),
                "source_timestamp_index_policy": str(row["source_timestamp_index_policy"]),
                "n_timesteps": int(row["n_timesteps"]),
                "weekday_weekend_preserved": bool(row["weekday_weekend_preserved"]),
                "duplicate_within_realization": multiplicity > 1,
                "duplicate_multiplicity": multiplicity,
            }
        )
    duplicate_groups = [
        {
            "source_member_id": member_id,
            "duplicate_multiplicity": len(indices),
            "duplicate_selection_indices": indices,
        }
        for member_id, indices in sorted(positions.items())
        if len(indices) > 1
    ]
    return {
        "schema_version": 1,
        "artifact_type": "ev_candidate_member_selection_manifest",
        "status": "candidate_member_selection_metadata_only",
        "decision_id": "EV-005B",
        "scenario": scenario_name,
        "planning_year": planning_year,
        "node_id": node_name,
        "component_id": component_name,
        "capacity_class": capacity_name,
        "cp_capacity_kw": capacity_kw,
        "required_members": requested,
        "component_stream": component_stream.manifest_record(),
        "replacement_enabled": True,
        "candidate_pool_member_count": len(pool),
        "selections": selections,
        "duplicate_member_groups": duplicate_groups,
        "policy": {
            "candidate_only": True,
            "held_out_access": False,
            "profile_arrays_loaded": False,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
            "m_sufficiency_claimed": False,
        },
    }



def ev_candidate_member_selection_manifest_set(
    candidate_member_reference: Mapping[str, Any],
    *,
    decisions_text: str,
    root_seed: int,
    sample_index: int,
    scenarios: Sequence[str] | None = None,
    materialized_timestamp_utc: str | None = None,
    source_candidate_member_reference_sha256: str | None = None,
) -> dict[str, object]:
    """Materialize candidate-only EV-005B member-selection manifests.

    This emits provenance rows only. It never opens generated profile arrays,
    held-out batches, or quarantined diagnostic batches.
    """

    members = _validated_candidate_member_rows(candidate_member_reference)
    _require_ev005b_approved(decisions_text)
    seed_tree = SeedTree(root_seed=_require_int(root_seed, "root_seed"))
    sample = _require_int(sample_index, "sample_index")
    if sample < 0:
        raise ValueError("sample_index must be non-negative")

    requirements = candidate_member_reference.get("scenario_node_requirements")
    if not isinstance(requirements, list):
        raise ValueError("EV member-selection manifest sets require scenario_node_requirements")
    requested_scenarios = None if scenarios is None else {_require_non_empty_string(item, "scenario") for item in scenarios}
    requirement_rows = [
        _validated_ev_selection_requirement_row(row)
        for row in requirements
        if requested_scenarios is None
        or (isinstance(row, dict) and str(row.get("scenario", "")).strip() in requested_scenarios)
    ]
    if not requirement_rows:
        raise ValueError("No EV scenario-node requirements match the requested scenarios")
    present_scenarios = {str(row["scenario"]) for row in requirement_rows}
    if requested_scenarios is not None and present_scenarios != requested_scenarios:
        missing = sorted(requested_scenarios - present_scenarios)
        raise ValueError(f"EV scenario-node requirements missing requested scenarios: {missing}")

    home_pool = _candidate_pool_for_component(members, EV_HOME_COMPONENT)
    public_pools = {
        capacity_class: _candidate_pool_for_component(
            members,
            EV_PUBLIC_COMPONENT,
            capacity_class=capacity_class,
        )
        for capacity_class, _capacity_kw, _share in EV_PUBLIC_SET_B_CAPACITY_MIX
    }
    timestamp = materialized_timestamp_utc or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    source_reference_sha = (
        None
        if source_candidate_member_reference_sha256 is None
        else _require_sha256(source_candidate_member_reference_sha256, "source_candidate_member_reference_sha256")
    )
    scenario_manifests: list[dict[str, object]] = []
    all_duplicate_summaries: list[dict[str, object]] = []

    for scenario in sorted(present_scenarios):
        scenario_rows = sorted(
            [row for row in requirement_rows if row["scenario"] == scenario],
            key=lambda item: str(item["node_id"]),
        )
        home_stream = seed_tree.component_stream(sample, EV_HOME_COMPONENT)
        public_stream = seed_tree.component_stream(sample, EV_PUBLIC_COMPONENT)
        home_rng = home_stream.rng()
        public_rng = public_stream.rng()

        total_home = sum(int(row["home_required_members"]) for row in scenario_rows)
        total_public_by_capacity = {
            capacity_class: sum(
                int(row["public_required_members_by_capacity_class"][capacity_class])
                for row in scenario_rows
            )
            for capacity_class, _capacity_kw, _share in EV_PUBLIC_SET_B_CAPACITY_MIX
        }
        home_indices = _draw_candidate_pool_indices(home_rng, len(home_pool), total_home)
        public_indices_by_capacity = {
            capacity_class: _draw_candidate_pool_indices(
                public_rng,
                len(public_pools[capacity_class]),
                total_public_by_capacity[capacity_class],
            )
            for capacity_class, _capacity_kw, _share in EV_PUBLIC_SET_B_CAPACITY_MIX
        }
        home_multiplicities = _member_multiplicities(home_pool, home_indices)
        public_multiplicities_by_capacity = {
            capacity_class: _member_multiplicities(public_pools[capacity_class], indices)
            for capacity_class, indices in public_indices_by_capacity.items()
        }

        node_manifests: list[dict[str, object]] = []
        home_offset = 0
        public_offsets = {capacity_class: 0 for capacity_class, _capacity_kw, _share in EV_PUBLIC_SET_B_CAPACITY_MIX}
        global_counters: dict[tuple[str, str | None], int] = {
            (EV_HOME_COMPONENT, None): 0,
            **{(EV_PUBLIC_COMPONENT, capacity_class): 0 for capacity_class, _kw, _share in EV_PUBLIC_SET_B_CAPACITY_MIX},
        }
        for row in scenario_rows:
            node_id = str(row["node_id"])
            home_count = int(row["home_required_members"])
            home_slice = home_indices[home_offset : home_offset + home_count]
            home_offset += home_count
            node_selections = _ev_selection_rows_from_indices(
                pool=home_pool,
                selected_indices=home_slice,
                multiplicities=home_multiplicities,
                scenario=scenario,
                planning_year=int(row["year"]),
                node_id=node_id,
                component_id=EV_HOME_COMPONENT,
                component_stream=home_stream,
                capacity_class=None,
                cp_capacity_kw=None,
                selection_count_at_node=home_count,
                global_start_index=global_counters[(EV_HOME_COMPONENT, None)],
            )
            global_counters[(EV_HOME_COMPONENT, None)] += home_count

            public_required = row["public_required_members_by_capacity_class"]
            for capacity_class, capacity_kw, _share in EV_PUBLIC_SET_B_CAPACITY_MIX:
                public_count = int(public_required[capacity_class])
                start = public_offsets[capacity_class]
                stop = start + public_count
                public_offsets[capacity_class] = stop
                public_slice = public_indices_by_capacity[capacity_class][start:stop]
                node_selections.extend(
                    _ev_selection_rows_from_indices(
                        pool=public_pools[capacity_class],
                        selected_indices=public_slice,
                        multiplicities=public_multiplicities_by_capacity[capacity_class],
                        scenario=scenario,
                        planning_year=int(row["year"]),
                        node_id=node_id,
                        component_id=EV_PUBLIC_COMPONENT,
                        component_stream=public_stream,
                        capacity_class=capacity_class,
                        cp_capacity_kw=capacity_kw,
                        selection_count_at_node=public_count,
                        global_start_index=global_counters[(EV_PUBLIC_COMPONENT, capacity_class)],
                    )
                )
                global_counters[(EV_PUBLIC_COMPONENT, capacity_class)] += public_count

            node_manifests.append(
                {
                    "scenario": scenario,
                    "planning_year": int(row["year"]),
                    "node_id": node_id,
                    "home_required_members": home_count,
                    "public_required_members": int(row["public_required_members"]),
                    "public_required_members_by_capacity_class": dict(public_required),
                    "selections": node_selections,
                }
            )

        scenario_duplicate_summary = [
            _duplicate_summary_record(
                scenario=scenario,
                component_id=EV_HOME_COMPONENT,
                capacity_class=None,
                selected_count=total_home,
                multiplicities=home_multiplicities,
            )
        ]
        scenario_duplicate_summary.extend(
            _duplicate_summary_record(
                scenario=scenario,
                component_id=EV_PUBLIC_COMPONENT,
                capacity_class=capacity_class,
                selected_count=total_public_by_capacity[capacity_class],
                multiplicities=public_multiplicities_by_capacity[capacity_class],
            )
            for capacity_class, _capacity_kw, _share in EV_PUBLIC_SET_B_CAPACITY_MIX
        )
        all_duplicate_summaries.extend(scenario_duplicate_summary)

        scenario_manifests.append(
            {
                "scenario": scenario,
                "planning_year": int(scenario_rows[0]["year"]),
                "node_count": len(scenario_rows),
                "home_required_members": total_home,
                "public_required_members": sum(total_public_by_capacity.values()),
                "public_required_members_by_capacity_class": dict(sorted(total_public_by_capacity.items())),
                "component_streams": {
                    EV_HOME_COMPONENT: home_stream.manifest_record(),
                    EV_PUBLIC_COMPONENT: public_stream.manifest_record(),
                },
                "node_manifests": node_manifests,
                "duplicate_summary": scenario_duplicate_summary,
            }
        )

    return {
        "schema_version": 1,
        "artifact_type": "ev_candidate_member_selection_manifest_set",
        "status": "candidate_member_selection_metadata_only",
        "task_id": "E2.S2",
        "decision_id": "EV-005B",
        "source_candidate_member_reference": "data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_member_reference.json",
        "source_candidate_member_reference_sha256": source_reference_sha,
        "materialized_timestamp_utc": timestamp,
        "root_seed": seed_tree.root_seed,
        "sample_index": sample,
        "seed_tree": {
            "protocol_id": "RNG-001",
            "sample_seed": seed_tree.sample_seed(sample),
        },
        "planning_year": _require_int(candidate_member_reference.get("planning_year"), "planning_year"),
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
        "scenario_count": len(scenario_manifests),
        "scenarios": scenario_manifests,
        "duplicate_summary": all_duplicate_summaries,
        "policy": {
            "candidate_only": True,
            "replacement_policy_id": "EV-005B",
            "replacement_enabled": True,
            "held_out_access": False,
            "quarantined_access": False,
            "profile_arrays_loaded": False,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
            "capacity_screen_performed": False,
            "manuscript_numbers_produced": False,
            "m_sufficiency_claimed": False,
        },
    }


def _validated_ev_selection_requirement_row(value: Any) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("EV scenario-node requirements must be mappings")
    public_by_capacity = _require_int_mapping(
        value.get("public_required_members_by_capacity_class"),
        "public_required_members_by_capacity_class",
    )
    expected_capacity_classes = {capacity_class for capacity_class, _kw, _share in EV_PUBLIC_SET_B_CAPACITY_MIX}
    if set(public_by_capacity) != expected_capacity_classes:
        raise ValueError("EV public requirements must cover every EV-008A capacity class exactly once")
    row = {
        "scenario": _require_non_empty_string(value.get("scenario"), "scenario"),
        "year": _require_int(value.get("year"), "year"),
        "node_id": _require_non_empty_string(value.get("node_id"), "node_id"),
        "home_required_members": _require_int(value.get("home_required_members"), "home_required_members"),
        "public_required_members": _require_int(value.get("public_required_members"), "public_required_members"),
        "public_required_members_by_capacity_class": dict(sorted(public_by_capacity.items())),
    }
    if int(row["home_required_members"]) < 0 or int(row["public_required_members"]) < 0:
        raise ValueError("EV scenario-node requirements must be nonnegative")
    if sum(public_by_capacity.values()) != int(row["public_required_members"]):
        raise ValueError("EV public capacity-class requirements must conserve node public total")
    return row


def _candidate_pool_for_component(
    members: Sequence[Mapping[str, object]],
    component_id: str,
    *,
    capacity_class: str | None = None,
) -> list[dict[str, object]]:
    pool = [
        dict(row)
        for row in members
        if row["component_id"] == component_id
        and (capacity_class is None or row.get("capacity_class") == capacity_class)
    ]
    if not pool:
        raise ValueError("No candidate EV source members match the requested component/capacity class")
    return pool


def _draw_candidate_pool_indices(rng: np.random.Generator, pool_size: int, count: int) -> list[int]:
    if count < 0:
        raise ValueError("EV member-selection counts must be nonnegative")
    if count == 0:
        return []
    return [int(index) for index in rng.choice(pool_size, size=count, replace=True)]


def _member_multiplicities(
    pool: Sequence[Mapping[str, object]],
    selected_indices: Sequence[int],
) -> Counter[str]:
    return Counter(str(pool[index]["source_member_id"]) for index in selected_indices)


def _ev_selection_rows_from_indices(
    *,
    pool: Sequence[Mapping[str, object]],
    selected_indices: Sequence[int],
    multiplicities: Mapping[str, int],
    scenario: str,
    planning_year: int,
    node_id: str,
    component_id: str,
    component_stream: ComponentStream,
    capacity_class: str | None,
    cp_capacity_kw: int | None,
    selection_count_at_node: int,
    global_start_index: int,
) -> list[dict[str, object]]:
    selections: list[dict[str, object]] = []
    for node_selection_index, pool_index in enumerate(selected_indices):
        row = pool[pool_index]
        member_id = str(row["source_member_id"])
        multiplicity = int(multiplicities[member_id])
        selections.append(
            {
                "node_id": node_id,
                "component_id": component_id,
                "capacity_class": capacity_class,
                "cp_capacity_kw": cp_capacity_kw,
                "selection_index": node_selection_index,
                "realization_selection_index": global_start_index + node_selection_index,
                "selection_pool_index": int(pool_index),
                "selection_count_at_node": selection_count_at_node,
                "source_member_id": member_id,
                "library_id": str(row["library_id"]),
                "partition": str(row["partition"]),
                "control_mode": str(row["control_mode"]),
                "batch_seed": int(row["batch_seed"]),
                "returned_profile_index": int(row["returned_profile_index"]),
                "candidate_processed_path": str(row["processed_path"]),
                "candidate_processed_sha256_file": str(row["candidate_processed_sha256_file"]),
                "duplicate_within_realization": multiplicity > 1,
                "duplicate_multiplicity": multiplicity,
            }
        )
    return selections


def _duplicate_summary_record(
    *,
    scenario: str,
    component_id: str,
    capacity_class: str | None,
    selected_count: int,
    multiplicities: Mapping[str, int],
) -> dict[str, object]:
    duplicate_values = [count for count in multiplicities.values() if count > 1]
    return {
        "scenario": scenario,
        "component_id": component_id,
        "capacity_class": capacity_class,
        "selected_count": selected_count,
        "unique_source_member_count": len(multiplicities),
        "duplicate_source_member_count": len(duplicate_values),
        "max_duplicate_multiplicity": max(duplicate_values, default=1),
    }


def _validated_candidate_member_rows(candidate_member_reference: Mapping[str, Any]) -> list[dict[str, object]]:
    if candidate_member_reference.get("artifact_type") != "ev_ic1_candidate_member_reference":
        raise ValueError("Expected EV IC-1 candidate member reference metadata")
    policy = candidate_member_reference.get("policy")
    if not isinstance(policy, dict) or policy.get("held_out_access") is not False:
        raise ValueError("EV member selection requires candidate-only metadata with held-out access blocked")
    if policy.get("profile_arrays_loaded") is not False:
        raise ValueError("EV member selection metadata must not load profile arrays")
    if policy.get("m_sufficiency_claimed") is not False:
        raise ValueError("EV member selection metadata must not claim M sufficiency")
    members = candidate_member_reference.get("candidate_members")
    if not isinstance(members, list):
        raise ValueError("EV member selection requires candidate_members rows")
    validated: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in members:
        if not isinstance(item, dict):
            raise ValueError("EV candidate member rows must be mappings")
        if item.get("partition") != "candidate":
            raise ValueError("EV member selection refuses non-candidate partitions")
        component_id = _require_non_empty_string(item.get("component_id"), "component_id")
        if component_id not in {EV_HOME_COMPONENT, EV_PUBLIC_COMPONENT}:
            raise ValueError("EV candidate member rows require a supported EV component_id")
        library_id = _require_non_empty_string(item.get("library_id"), "library_id")
        member_id = _require_non_empty_string(item.get("source_member_id"), "source_member_id")
        path = _require_non_empty_string(item.get("processed_path"), "processed_path")
        normalized_path = path.replace("\\", "/")
        if "/raw/" in normalized_path or "held_out" in normalized_path or "quarantined" in normalized_path:
            raise ValueError("EV member selection refuses raw, held-out, or quarantined paths")
        processed_sha = _require_sha256(
            item.get("candidate_processed_sha256_file"),
            "candidate_processed_sha256_file",
        )
        if item.get("calendar_mapping_rule_id") != EV_CALENDAR_MAPPING_RULE_ID:
            raise ValueError("EV member selection requires EV-CAL-001 calendar provenance")
        if item.get("calendar_mapping_rule_version") != EV_CALENDAR_MAPPING_RULE_VERSION:
            raise ValueError("EV member selection requires EV-CAL-001 rule-version provenance")
        if item.get("source_calendar_id") != EV_SOURCE_CALENDAR_ID:
            raise ValueError("EV member selection requires source-calendar provenance")
        if item.get("target_calendar_id") != EV_TARGET_CALENDAR_ID:
            raise ValueError("EV member selection requires target-calendar provenance")
        if item.get("source_timestamp_index_policy") != "target_index_i_uses_source_index_i":
            raise ValueError("EV member selection requires ordinal source-index provenance")
        if _require_int(item.get("n_timesteps"), "n_timesteps") != EXPECTED_FULL_YEAR_STEPS:
            raise ValueError("EV member selection requires complete 35,040-step member metadata")
        if item.get("weekday_weekend_preserved") is not False:
            raise ValueError("EV member selection requires EV-CAL-001 weekday/weekend limitation provenance")
        _require_non_empty_string(item.get("control_mode"), "control_mode")
        key = (component_id, library_id, member_id)
        if key in seen:
            raise ValueError("EV candidate source-member identity must be unique")
        seen.add(key)
        row = dict(item)
        row["processed_path"] = path
        row["candidate_processed_sha256_file"] = processed_sha
        row["batch_seed"] = _require_int(item.get("batch_seed"), "batch_seed")
        row["returned_profile_index"] = _require_int(
            item.get("returned_profile_index"),
            "returned_profile_index",
        )
        validated.append(row)
    return validated


def _require_ev005b_approved(decisions_text: str) -> None:
    if not isinstance(decisions_text, str) or "EV-005B" not in decisions_text:
        raise PermissionError("EV-005B approval is required before EV member selection")
    for line in decisions_text.splitlines():
        if line.startswith("| EV-005B |"):
            cells = [cell.strip().lower() for cell in line.strip().strip("|").split("|")]
            status = cells[6] if len(cells) > 6 else ""
            signoff = cells[7] if len(cells) > 7 else ""
            if status.startswith("approved") and signoff not in {"", "--"}:
                return
            raise PermissionError("EV-005B remains unapproved; EV member selection is blocked")
    raise PermissionError("EV-005B approval row is required before EV member selection")
def ev_member_selection_implementation_plan() -> dict[str, object]:
    """Return the EV-005B candidate member-selection implementation status."""

    return {
        "schema_version": 1,
        "artifact_type": "ev_member_selection_implementation_plan",
        "task_id": "E2.S2",
        "status": "ev005b_approved_candidate_member_selection_ready",
        "approved_decision": "EV-005B",
        "proposed_policy_assumption": "A_charge_point_level_with_replacement",
        "implementation_authorization": {
            "candidate_member_selection_allowed": True,
            "profile_array_loading_allowed": False,
            "reason": "EV-005B is PI-approved for candidate member-selection implementation only",
            "current_authorized_step": (
                "Produce candidate-only member-selection metadata rows from committed manifests and "
                "RNG-001 ComponentStream objects without changing source-library adequacy claims."
            ),
        },
        "inputs_expected_after_approval": [
            "data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_adapter_artifact.json",
            "data/metadata/ev_adoption/e2_s2_public_set_b_capacity_allocation_readiness.json",
            "data/metadata/ev_adoption/e2_s2_ev005_replacement_policy_packet.json",
            "RNG-001 SeedTree.component_stream(sample_index, component='ev_home')",
            "RNG-001 SeedTree.component_stream(sample_index, component='ev_public')",
        ],
        "planned_algorithm_after_approval": [
            "verify committed candidate manifest paths and processed SHA-256 expectations before any array load",
            "derive scenario/node/component/capacity-class required counts from the candidate adapter artifacts",
            "require EV home draws to use the ev_home ComponentStream and public draws to use ev_public",
            "select source-member rows with explicit charge-point-level replacement under approved EV-005B",
            "preserve duplicate source-member selections as repeated manifest rows with multiplicity counters",
            "materialize selection metadata separately from mapped profile arrays so provenance can be reviewed first",
        ],
        "manifest_fields": [
            "scenario",
            "planning_year",
            "sample_index",
            "root_seed",
            "component_id",
            "component_stream_id",
            "component_seed",
            "node_id",
            "capacity_class",
            "cp_capacity_kw",
            "selection_index",
            "selection_count_at_node",
            "replacement_policy_id",
            "replacement_enabled",
            "source_member_id",
            "batch_seed",
            "returned_profile_index",
            "candidate_processed_path",
            "candidate_processed_sha256_file",
            "selection_pool_index",
            "library_id",
            "partition",
            "control_mode",
            "calendar_mapping_rule_id",
            "calendar_mapping_rule_version",
            "source_calendar_id",
            "target_calendar_id",
            "source_timestamp_index_policy",
            "duplicate_within_realization",
            "duplicate_multiplicity",
        ],
        "duplicate_member_logging": {
            "required": True,
            "duplicate_key": [
                "scenario",
                "sample_index",
                "component_id",
                "capacity_class",
                "source_member_id",
            ],
            "fields": [
                "duplicate_within_realization",
                "duplicate_multiplicity",
                "duplicate_selection_indices",
            ],
            "interpretation": (
                "Duplicate rows are bootstrap multiplicities for physical charge points, not new "
                "unique source profiles and not evidence that M is sufficient."
            ),
        },
        "rng001_stream_usage": {
            "construct_streams_in_calling_context": True,
            "do_not_accept_raw_integer_seed_in_sampler": True,
            "home_component_stream": "ev_home",
            "public_component_stream": "ev_public",
            "stream_identity_must_be_recorded": True,
            "alpha_endpoint_treatment_labels_do_not_change_aleatory_identity": True,
        },
        "preimplementation_checks": [
            "EV-005B status is approved in DECISIONS.md before candidate member-selection manifests are produced",
            "candidate-only adapter artifact blocks held-out and quarantined partitions",
            "candidate processed checksums verify in the consuming worktree before profile arrays load",
            "scenario/node totals conserve EV-007A/A-014 counts after capacity-class allocation",
            "member IDs, batch seeds, and returned profile indices are unique in source-member reference rows",
            "duplicate-member report is produced for every realized sample when replacement is enabled",
        ],
        "blocked_actions_after_ev005b_approval": [
            "profile_array_loading",
            "held_out_or_quarantined_partition_access",
            "integrated_net_load_or_event_analysis",
            "m_sufficiency_claim",
            "manuscript_number_generation",
        ],
        "non_claims": {
            "ev005b_approved": True,
            "production_member_draws_performed_in_this_plan": False,
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



def ev_ic1_component_input_scaffold_artifact(
    candidate_adapter_artifact: Mapping[str, Any],
    public_capacity_artifact: Mapping[str, Any],
    candidate_member_reference: Mapping[str, Any],
    selection_manifest_set: Mapping[str, Any],
    *,
    candidate_selection_manifest_sha256: str | None = None,
) -> dict[str, object]:
    """Build an array-free EV component-input scaffold for IC-1.

    The scaffold is intentionally a manifest bridge: it proves that approved
    EV-007A/A-014 counts, EV-008A capacity strata, EV-005B selections, and
    EV-CAL-001 calendar metadata agree before any generated profile arrays are
    loaded by a future Agent A adapter.
    """

    if candidate_adapter_artifact.get("artifact_type") != "ev_to_ic1_candidate_adapter_artifact":
        raise ValueError("Expected an EV-to-IC-1 candidate adapter artifact")
    if public_capacity_artifact.get("artifact_type") != "ev_public_set_b_capacity_allocation_readiness":
        raise ValueError("Expected EV public Set B capacity allocation readiness metadata")
    if candidate_member_reference.get("artifact_type") != "ev_ic1_candidate_member_reference":
        raise ValueError("Expected EV candidate member reference metadata")
    if selection_manifest_set.get("artifact_type") != "ev_candidate_member_selection_manifest_set":
        raise ValueError("Expected EV-005B candidate member-selection manifest set")

    for label, artifact in (
        ("candidate adapter", candidate_adapter_artifact),
        ("public capacity", public_capacity_artifact),
        ("candidate member reference", candidate_member_reference),
    ):
        policy = artifact.get("policy")
        if not isinstance(policy, dict):
            raise ValueError(f"{label} artifact must include policy flags")
        if policy.get("held_out_access") is not False:
            raise ValueError(f"{label} artifact must block held-out access")
        if policy.get("profile_arrays_loaded") not in {False, None} and policy.get("profile_arrays_opened") not in {False, None}:
            raise ValueError(f"{label} artifact must not load EV profile arrays")
        if policy.get("m_sufficiency_claimed") is not False:
            raise ValueError(f"{label} artifact must not claim EV library sufficiency")
        if policy.get("integrated_analysis_performed") is not False:
            raise ValueError(f"{label} artifact must not include integrated analysis")

    selection_policy = selection_manifest_set.get("policy")
    if not isinstance(selection_policy, dict):
        raise ValueError("EV selection manifest set must include policy flags")
    if selection_policy.get("candidate_only") is not True:
        raise ValueError("EV component-input scaffold requires candidate-only selections")
    blocked_selection_flags = {
        "held_out_access": False,
        "quarantined_access": False,
        "profile_arrays_loaded": False,
        "integrated_analysis_performed": False,
        "event_or_p_e_analysis_performed": False,
        "capacity_screen_performed": False,
        "manuscript_numbers_produced": False,
        "m_sufficiency_claimed": False,
    }
    for key, expected in blocked_selection_flags.items():
        if selection_policy.get(key) is not expected:
            raise ValueError(f"EV selection manifest policy {key} must be {expected!r}")
    if selection_policy.get("replacement_policy_id") != "EV-005B" or selection_policy.get("replacement_enabled") is not True:
        raise ValueError("EV component-input scaffold requires approved EV-005B replacement selections")

    source_ref_sha = _require_sha256(
        selection_manifest_set.get("source_candidate_member_reference_sha256"),
        "source_candidate_member_reference_sha256",
    )
    if candidate_selection_manifest_sha256 is not None:
        candidate_selection_manifest_sha256 = _require_sha256(
            candidate_selection_manifest_sha256,
            "candidate_selection_manifest_sha256",
        )

    adapter_totals = candidate_adapter_artifact.get("scenario_totals")
    if not isinstance(adapter_totals, dict):
        raise ValueError("Candidate adapter artifact must include scenario_totals")
    public_totals = public_capacity_artifact.get("scenario_totals")
    if not isinstance(public_totals, dict):
        raise ValueError("Public capacity artifact must include scenario_totals")
    member_counts = candidate_member_reference.get("candidate_member_count_by_component")
    if member_counts != {EV_HOME_COMPONENT: 1000, EV_PUBLIC_COMPONENT: 1200}:
        raise ValueError("EV component-input scaffold requires verified Set A/B candidate member counts")

    allocation_rows = candidate_adapter_artifact.get("node_allocations")
    if not isinstance(allocation_rows, list):
        raise ValueError("Candidate adapter artifact must include node_allocations")
    selection_scenarios = selection_manifest_set.get("scenarios")
    if not isinstance(selection_scenarios, list):
        raise ValueError("EV selection manifest set must include scenarios")
    public_scenarios = public_capacity_artifact.get("scenario_allocations")
    if not isinstance(public_scenarios, list):
        raise ValueError("Public capacity artifact must include scenario_allocations")

    allocation_by_scenario = {
        _require_non_empty_string(row.get("scenario"), "scenario"): row
        for row in allocation_rows
        if isinstance(row, dict)
    }
    selection_by_scenario = {
        _require_non_empty_string(row.get("scenario"), "scenario"): row
        for row in selection_scenarios
        if isinstance(row, dict)
    }
    public_by_scenario = {
        _require_non_empty_string(row.get("scenario"), "scenario"): row
        for row in public_scenarios
        if isinstance(row, dict)
    }
    if set(allocation_by_scenario) != set(selection_by_scenario) or set(allocation_by_scenario) != set(public_by_scenario):
        raise ValueError("EV scenario coverage must match across allocation, public capacity, and selection metadata")

    node_ids: set[str] | None = None
    scenario_records: list[dict[str, object]] = []
    for scenario in sorted(allocation_by_scenario):
        allocation = allocation_by_scenario[scenario]
        selection = selection_by_scenario[scenario]
        public_record = public_by_scenario[scenario]
        home_by_node = _require_int_mapping(allocation.get("home_by_node"), f"{scenario} home_by_node")
        public_by_node = _require_int_mapping(allocation.get("public_by_node"), f"{scenario} public_by_node")
        public_by_class = public_record.get("public_by_node_by_capacity_class")
        if not isinstance(public_by_class, dict):
            raise ValueError("Public capacity artifact must include node capacity-class allocations")
        current_nodes = set(home_by_node)
        if current_nodes != set(public_by_node) or current_nodes != set(public_by_class):
            raise ValueError("EV home/public/capacity allocations must cover the same nodes")
        if node_ids is None:
            node_ids = current_nodes
        elif node_ids != current_nodes:
            raise ValueError("EV component-input scenarios must cover one stable node set")

        expected_home = sum(home_by_node.values())
        expected_public = sum(public_by_node.values())
        totals = adapter_totals.get(scenario)
        if totals != {"home": expected_home, "public": expected_public}:
            raise ValueError("EV scenario totals do not match node allocations")
        if public_totals.get(scenario, {}).get("public") != expected_public:
            raise ValueError("EV public capacity totals do not match public node allocation")
        if selection.get("home_required_members") != expected_home or selection.get("public_required_members") != expected_public:
            raise ValueError("EV-005B selection totals do not match EV adoption requirements")

        node_manifests = selection.get("node_manifests")
        if not isinstance(node_manifests, list):
            raise ValueError("EV selection scenarios must include node manifests")
        selection_nodes = {
            _require_non_empty_string(row.get("node_id"), "selection node_id"): row
            for row in node_manifests
            if isinstance(row, dict)
        }
        if set(selection_nodes) != current_nodes:
            raise ValueError("EV selection manifest nodes must match A-014 allocation nodes")

        scenario_node_records: list[dict[str, object]] = []
        for node_id in sorted(current_nodes):
            class_row = public_by_class[node_id]
            if not isinstance(class_row, dict):
                raise ValueError("EV public capacity node allocation rows must be mappings")
            class_counts = _require_int_mapping(class_row, f"{scenario} {node_id} public_by_capacity_class")
            if sum(class_counts.values()) != public_by_node[node_id]:
                raise ValueError("EV public capacity-class counts must conserve each node total")
            node_selection = selection_nodes[node_id]
            if node_selection.get("home_required_members") != home_by_node[node_id]:
                raise ValueError("EV home selection count does not match node allocation")
            if node_selection.get("public_required_members") != public_by_node[node_id]:
                raise ValueError("EV public selection count does not match node allocation")
            selections = node_selection.get("selections")
            if not isinstance(selections, list):
                raise ValueError("EV selection node manifest must include selections")
            if len(selections) != home_by_node[node_id] + public_by_node[node_id]:
                raise ValueError("EV selection row count must match node charge-point count")
            scenario_node_records.append(
                {
                    "node_id": node_id,
                    "home_charge_points": home_by_node[node_id],
                    "public_charge_points": public_by_node[node_id],
                    "public_charge_points_by_capacity_class": dict(sorted(class_counts.items())),
                    "selection_manifest_pointer": {
                        "scenario": scenario,
                        "node_id": node_id,
                        "selection_row_count": len(selections),
                        "selection_rows_are_in_source_manifest": True,
                    },
                }
            )

        scenario_records.append(
            {
                "scenario": scenario,
                "planning_year": _require_int(allocation.get("year"), "planning_year"),
                "node_count": len(current_nodes),
                "home_charge_points": expected_home,
                "public_charge_points": expected_public,
                "public_charge_points_by_capacity_class": public_record.get("capacity_class_totals"),
                "component_streams": selection.get("component_streams"),
                "node_inputs": scenario_node_records,
                "total_conservation_verified": True,
                "selection_counts_verified": True,
            }
        )

    stable_node_ids = tuple(sorted(node_ids or ()))
    if len(stable_node_ids) != 115:
        raise ValueError("EV IC-1 component-input scaffold currently requires 115 SimBench load nodes")
    calendar = candidate_member_reference.get("calendar_mapping")
    if not isinstance(calendar, dict) or calendar.get("rule_id") != EV_CALENDAR_MAPPING_RULE_ID:
        raise ValueError("EV component-input scaffold requires EV-CAL-001 calendar metadata")
    if calendar.get("n_timesteps") != EXPECTED_FULL_YEAR_STEPS:
        raise ValueError("EV component-input scaffold requires complete 35,040-step profiles")

    return {
        "schema_version": 1,
        "artifact_type": "ev_ic1_component_input_scaffold",
        "artifact_id": "e2_s2_ev_ic1_component_input_scaffold",
        "status": "accepted_metadata_only_for_ic1_component_input_scaffold",
        "task_id": "E2.S2",
        "planning_year": 2035,
        "component_kind": "ev",
        "component_ids": [EV_HOME_COMPONENT, EV_PUBLIC_COMPONENT],
        "source_ids": ["D-002", "D-010"],
        "decision_ids": ["EV-003", "EV-004", "EV-005", "EV-005B", "EV-007A", "EV-008A", "EV-CAL-001", "RNG-001", "A-014"],
        "source_artifacts": {
            "candidate_adapter_artifact": "data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_adapter_artifact.json",
            "public_capacity_artifact": "data/metadata/ev_adoption/e2_s2_public_set_b_capacity_allocation_readiness.json",
            "candidate_member_reference": "data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_member_reference.json",
            "candidate_member_reference_sha256": source_ref_sha,
            "candidate_selection_manifest_set": "data/metadata/ev_adoption/e2_s2_ev005b_candidate_selection_manifests.json.gz",
            "candidate_selection_manifest_set_sha256": candidate_selection_manifest_sha256,
        },
        "ic1_accepted_component_adapter_artifact": {
            "artifact_id": "e2_s2_ev_ic1_component_input_scaffold",
            "kind": "ev",
            "source_id": "elaadnl_ev_candidate_component_input_scaffold",
            "member_id": "ev005b_candidate_selection_manifest_set_root20260722_sample0",
            "node_ids": list(stable_node_ids),
            "calendar_id": EV_TARGET_CALENDAR_ID,
            "timestep_seconds": 900,
            "shared_weather_driver_id": None,
            "provenance": {
                "source_selection_manifest": "data/metadata/ev_adoption/e2_s2_ev005b_candidate_selection_manifests.json.gz",
                "candidate_member_reference_sha256": source_ref_sha,
                "calendar_mapping_rule_id": EV_CALENDAR_MAPPING_RULE_ID,
                "calendar_mapping_rule_version": EV_CALENDAR_MAPPING_RULE_VERSION,
                "replacement_policy_id": "EV-005B",
            },
        },
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
        "scenario_inputs": scenario_records,
        "candidate_member_counts": {
            "home": 1000,
            "public": 1200,
            "public_by_capacity_class": candidate_member_reference.get("public_candidate_member_count_by_capacity_class"),
        },
        "selection_manifest_summary": {
            "root_seed": selection_manifest_set.get("root_seed"),
            "sample_index": selection_manifest_set.get("sample_index"),
            "seed_tree": selection_manifest_set.get("seed_tree"),
            "duplicate_summary": selection_manifest_set.get("duplicate_summary"),
            "scenario_count": selection_manifest_set.get("scenario_count"),
        },
        "loading_preconditions": {
            "verify_candidate_selection_manifest_set_sha256_before_use": True,
            "verify_candidate_processed_file_checksums_before_profile_loading": True,
            "load_only_candidate_processed_profile_arrays": True,
            "apply_ev_cal001_ordinal_mapping_before_ic1_aggregation": True,
        },
        "policy": {
            "candidate_libraries_only": True,
            "held_out_access": False,
            "quarantined_access": False,
            "profile_arrays_loaded": False,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
            "capacity_screen_performed": False,
            "manuscript_numbers_produced": False,
            "m_sufficiency_claimed": False,
            "final_low_middle_high_branch_selected": False,
        },
    }

def a014_executable_adoption_artifact(
    config: dict[str, Any],
    *,
    source_config_path: str = "configs/scenarios.yaml",
    source_config_sha256: str | None = None,
    preview_artifact_path: str = "data/metadata/ev_adoption/e2_s6_a014_alkmaar_allocation_preview.json",
    preview_artifact_sha256: str | None = None,
) -> dict[str, object]:
    """Build the accepted per-node EV adoption allocation artifact for IC-1.

    This is an adoption-count artifact only. It materializes EV-007A/A-014
    counts and node allocations, but does not select a final scenario branch or
    load any EV profile arrays.
    """

    validate_adoption_scenarios_config(config)
    if config["local_grid_scenarios"].get("status") != "approved":
        raise ValueError("Executable A-014 adoption artifact requires approved EV-007A local totals")
    if config["allocation"].get("status") != "approved":
        raise ValueError("Executable A-014 adoption artifact requires approved A-014 node weights")
    if source_config_sha256 is not None:
        source_config_sha256 = _require_sha256(source_config_sha256, "source_config_sha256")
    if preview_artifact_sha256 is not None:
        preview_artifact_sha256 = _require_sha256(preview_artifact_sha256, "preview_artifact_sha256")

    scenarios = {item.scenario: item for item in adoption_scenarios(config)}
    if set(scenarios) != {"low", "middle", "high"}:
        raise ValueError("Executable A-014 adoption artifact requires low/middle/high declared branches")
    allocations = adoption_node_allocations(config)
    if {item.scenario for item in allocations} != set(scenarios):
        raise ValueError("Executable A-014 adoption artifact scenario coverage mismatch")

    weight_records = config["allocation"].get("node_weights")
    if not isinstance(weight_records, list):
        raise ValueError("Executable A-014 adoption artifact requires materialized node weights")
    node_weights: list[dict[str, object]] = []
    for record in weight_records:
        if not isinstance(record, dict):
            raise ValueError("A-014 node weight records must be mappings")
        node_id = _require_non_empty_string(record.get("node_id"), "node_id")
        weight = float(record.get("weight"))
        if not np.isfinite(weight) or weight < 0.0:
            raise ValueError("A-014 node weights must be finite and non-negative")
        node_weights.append(
            {
                "node_id": node_id,
                "source_load_index": _require_int(record.get("source_load_index"), "source_load_index"),
                "weight": weight,
                "weight_share": float(record.get("weight_share")),
            }
        )
    if len(node_weights) != 115 or len({row["node_id"] for row in node_weights}) != len(node_weights):
        raise ValueError("Executable A-014 adoption artifact requires 115 unique node weights")
    if not np.isclose(sum(float(row["weight_share"]) for row in node_weights), 1.0):
        raise ValueError("A-014 node weight shares must sum to one")

    allocation_records: list[dict[str, object]] = []
    node_ids: tuple[str, ...] | None = None
    for allocation in sorted(allocations, key=lambda item: item.scenario):
        scenario = scenarios[allocation.scenario]
        current_nodes = tuple(sorted(allocation.home_by_node))
        if current_nodes != tuple(sorted(allocation.public_by_node)):
            raise ValueError("A-014 home/public allocations must cover the same nodes")
        if node_ids is None:
            node_ids = current_nodes
        elif node_ids != current_nodes:
            raise ValueError("A-014 scenario allocations must cover one stable node set")
        if allocation.total_home_charge_points != scenario.home_charge_points:
            raise ValueError("A-014 home allocation total does not match EV-007A local count")
        if allocation.total_public_charge_points != scenario.public_charge_points:
            raise ValueError("A-014 public allocation total does not match EV-007A local count")
        node_records = [
            {
                "node_id": node_id,
                "home_charge_points": allocation.home_by_node[node_id],
                "public_charge_points": allocation.public_by_node[node_id],
            }
            for node_id in current_nodes
        ]
        allocation_records.append(
            {
                "scenario": allocation.scenario,
                "planning_year": allocation.year,
                "home_charge_points": scenario.home_charge_points,
                "public_charge_points": scenario.public_charge_points,
                "node_count": len(current_nodes),
                "node_allocations": node_records,
                "provenance": scenario.provenance,
                "total_conservation_verified": True,
                "nonnegative_integer_counts_verified": True,
            }
        )

    stable_node_ids = tuple(node_ids or ())
    if len(stable_node_ids) != 115:
        raise ValueError("Executable A-014 adoption artifact requires 115 node IDs")
    selected_cluster = config.get("local_count_workflow", {}).get("selected_cluster", {})
    if not isinstance(selected_cluster, dict):
        selected_cluster = {}
    source_ids = config.get("source_ids")
    if not isinstance(source_ids, dict):
        raise ValueError("Executable A-014 adoption artifact requires source IDs")

    return {
        "schema_version": 1,
        "artifact_type": "a014_executable_ev_adoption_allocation_artifact",
        "artifact_id": "e2_s6_a014_alkmaar_executable_adoption_artifact",
        "status": "accepted_executable_per_node_ev_adoption_allocation",
        "task_id": "E2.S6",
        "planning_year": 2035,
        "source_ids": ["D-010"],
        "decision_ids": ["EV-007", "EV-007A", "A-014"],
        "source_artifacts": {
            "scenario_config": source_config_path,
            "scenario_config_sha256": source_config_sha256,
            "historical_preview_artifact": preview_artifact_path,
            "historical_preview_artifact_sha256": preview_artifact_sha256,
            "local_count_metadata": "data/metadata/ev_adoption/e2_s6_local_adoption_counts_metadata.json",
        },
        "selected_local_proxy": {
            "area_type": selected_cluster.get("area_type", "municipalities"),
            "area_identifier": selected_cluster.get("area_identifier", "GM0361"),
            "name": selected_cluster.get("name", "Alkmaar"),
            "governing_decision": "EV-007A",
        },
        "allocation_method": {
            "method_id": "A-014",
            "status": "approved",
            "stage": "second_stage_after_ev007_local_totals",
            "weight_column": "p_mw",
            "integer_rounding": "largest_remainder_ties_by_node_id",
            "node_weight_source": config["allocation"].get("node_weight_source"),
        },
        "scenario_selection": {
            "declared_branches": ["low", "middle", "high"],
            "final_low_middle_high_branch_selected": False,
            "selection_status": config["local_grid_scenarios"].get("scenario_selection_status"),
        },
        "node_axis": {
            "node_ids": list(stable_node_ids),
            "node_count": len(stable_node_ids),
            "node_axis_order": "sorted_node_id",
        },
        "node_weights": node_weights,
        "scenario_allocations": allocation_records,
        "scenario_totals": {
            record["scenario"]: {
                "home": record["home_charge_points"],
                "public": record["public_charge_points"],
            }
            for record in allocation_records
        },
        "policy": {
            "executable_adoption_counts": True,
            "candidate_profile_arrays_loaded": False,
            "held_out_access": False,
            "quarantined_access": False,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
            "capacity_screen_performed": False,
            "final_low_middle_high_branch_selected": False,
            "m_sufficiency_claimed": False,
            "manuscript_numbers_produced": False,
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
