"""Baseline load trajectory scaffold for complete-calendar aleatory samples."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
from typing import Sequence
from zoneinfo import ZoneInfo

import numpy as np


EXPECTED_STEP_SECONDS = 15 * 60
BASELINE_COMPONENT = "baseline_load"
COMMON_CALENDAR_COMPONENTS = ("baseline", "ev", "hp", "pv")


@dataclass(frozen=True)
class BaselineTrajectoryMetadata:
    """Manifestable metadata for one complete baseline load trajectory."""

    component: str
    trajectory_id: str
    source_id: str
    units: str
    calendar_timezone: str
    n_timesteps: int
    n_series: int
    first_timestamp: str
    last_timestamp: str
    step_minutes: int
    time_axis_sha256: str
    values_sha256: str
    preserves_temporal_order: bool = True
    weekday_weekend_preserved: bool = True
    seasonal_order_preserved: bool = True
    congestion_evaluated: bool = False
    adequacy_certified: bool = False

    def manifest_record(self) -> dict[str, bool | int | str]:
        return {
            "component": self.component,
            "trajectory_id": self.trajectory_id,
            "source_id": self.source_id,
            "units": self.units,
            "calendar_timezone": self.calendar_timezone,
            "n_timesteps": self.n_timesteps,
            "n_series": self.n_series,
            "first_timestamp": self.first_timestamp,
            "last_timestamp": self.last_timestamp,
            "step_minutes": self.step_minutes,
            "time_axis_sha256": self.time_axis_sha256,
            "values_sha256": self.values_sha256,
            "preserves_temporal_order": self.preserves_temporal_order,
            "weekday_weekend_preserved": self.weekday_weekend_preserved,
            "seasonal_order_preserved": self.seasonal_order_preserved,
            "congestion_evaluated": self.congestion_evaluated,
            "adequacy_certified": self.adequacy_certified,
        }


@dataclass(frozen=True)
class BaselineLoadTrajectory:
    """Complete baseline load trajectory on the canonical 15-minute calendar."""

    timestamps: tuple[datetime, ...]
    load_kw: np.ndarray
    trajectory_id: str
    source_id: str
    units: str = "kW"

    def __post_init__(self) -> None:
        normalized_timestamps = _validate_time_axis(self.timestamps)
        normalized_load = _validate_load_values(self.load_kw, len(normalized_timestamps))
        object.__setattr__(self, "timestamps", normalized_timestamps)
        object.__setattr__(self, "load_kw", normalized_load)
        _require_non_empty_string(self.trajectory_id, "trajectory_id")
        _require_non_empty_string(self.source_id, "source_id")
        _require_non_empty_string(self.units, "units")

    @property
    def n_timesteps(self) -> int:
        return int(self.load_kw.shape[0])

    @property
    def n_series(self) -> int:
        if self.load_kw.ndim == 1:
            return 1
        return int(self.load_kw.shape[1])

    @property
    def calendar_timezone(self) -> str:
        zone = self.timestamps[0].tzinfo
        return getattr(zone, "key", None) or str(zone)

    def metadata(self) -> BaselineTrajectoryMetadata:
        return BaselineTrajectoryMetadata(
            component=BASELINE_COMPONENT,
            trajectory_id=self.trajectory_id,
            source_id=self.source_id,
            units=self.units,
            calendar_timezone=self.calendar_timezone,
            n_timesteps=self.n_timesteps,
            n_series=self.n_series,
            first_timestamp=self.timestamps[0].isoformat(),
            last_timestamp=self.timestamps[-1].isoformat(),
            step_minutes=15,
            time_axis_sha256=_hash_json([item.isoformat() for item in self.timestamps]),
            values_sha256=hashlib.sha256(np.ascontiguousarray(self.load_kw).tobytes()).hexdigest(),
        )

    def values(self, *, copy: bool = True) -> np.ndarray:
        if copy:
            return self.load_kw.copy()
        return self.load_kw

    def weekday_weekend_labels(self) -> tuple[str, ...]:
        return tuple("weekend" if item.weekday() >= 5 else "weekday" for item in self.timestamps)

    def season_labels(self) -> tuple[str, ...]:
        return tuple(_meteorological_season(item.month) for item in self.timestamps)

    def require_calendar(self, expected_timestamps: Sequence[datetime]) -> None:
        expected = _validate_time_axis(expected_timestamps)
        if self.timestamps != expected:
            raise ValueError("Baseline trajectory timestamps do not match the canonical calendar")


@dataclass(frozen=True)
class BaselineTrajectoryLibrary:
    """Collection of complete baseline trajectories sharing one calendar."""

    trajectories: tuple[BaselineLoadTrajectory, ...]

    def __post_init__(self) -> None:
        if not self.trajectories:
            raise ValueError("Baseline trajectory library cannot be empty")
        reference = self.trajectories[0].timestamps
        for trajectory in self.trajectories:
            # ALEA-001 requires complete component paths on one calendar; a
            # mismatch here would silently desynchronize baseline from EV/HP/PV.
            if trajectory.timestamps != reference:
                raise ValueError("All baseline trajectories must share one canonical calendar")

    @property
    def n_trajectories(self) -> int:
        return len(self.trajectories)

    @property
    def timestamps(self) -> tuple[datetime, ...]:
        return self.trajectories[0].timestamps

    def trajectory(self, index: int) -> BaselineLoadTrajectory:
        if index < 0 or index >= len(self.trajectories):
            raise IndexError("baseline trajectory index out of range")
        return self.trajectories[index]

    def metadata_records(self) -> tuple[dict[str, bool | int | str], ...]:
        return tuple(trajectory.metadata().manifest_record() for trajectory in self.trajectories)


@dataclass(frozen=True)
class ComponentCalendarFootprint:
    """Manifestable timestamp footprint for one E2 component trajectory."""

    component: str
    member_id: str
    source_id: str
    timestamps_utc: tuple[datetime, ...]
    shared_weather_driver_id: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_string(self.component, "component")
        _require_non_empty_string(self.member_id, "member_id")
        _require_non_empty_string(self.source_id, "source_id")
        timestamps = _validate_utc_time_axis(self.timestamps_utc)
        object.__setattr__(self, "timestamps_utc", timestamps)
        if self.shared_weather_driver_id is not None:
            _require_non_empty_string(self.shared_weather_driver_id, "shared_weather_driver_id")

    @property
    def n_timesteps(self) -> int:
        return len(self.timestamps_utc)

    @property
    def cadence_seconds(self) -> int:
        if len(self.timestamps_utc) == 1:
            return 0
        return int((self.timestamps_utc[1] - self.timestamps_utc[0]).total_seconds())

    @property
    def time_axis_sha256(self) -> str:
        return _hash_json([item.isoformat() for item in self.timestamps_utc])

    def manifest_record(self) -> dict[str, bool | int | str | None]:
        return {
            "component": self.component,
            "member_id": self.member_id,
            "source_id": self.source_id,
            "n_timesteps": self.n_timesteps,
            "cadence_seconds": self.cadence_seconds,
            "first_timestamp_utc": self.timestamps_utc[0].isoformat(),
            "last_timestamp_utc": self.timestamps_utc[-1].isoformat(),
            "time_axis_sha256": self.time_axis_sha256,
            "shared_weather_driver_id": self.shared_weather_driver_id,
            "complete_temporal_path": True,
            "preserves_temporal_order": True,
        }


@dataclass(frozen=True)
class ComponentCalendarReadiness:
    """Readiness record for aligned E2 components before IC-1 aggregation."""

    calendar_id: str
    local_year: int
    timezone: str
    n_timesteps: int
    cadence_seconds: int
    first_timestamp_utc: str
    last_timestamp_utc: str
    time_axis_sha256: str
    component_records: tuple[dict[str, bool | int | str | None], ...]
    shared_weather_driver_id: str
    aligned_on_common_calendar: bool = True
    congestion_evaluated: bool = False
    adequacy_certified: bool = False
    manuscript_numbers_produced: bool = False

    def manifest_record(self) -> dict[str, bool | int | str | tuple[dict[str, bool | int | str | None], ...]]:
        return {
            "calendar_id": self.calendar_id,
            "local_year": self.local_year,
            "timezone": self.timezone,
            "n_timesteps": self.n_timesteps,
            "cadence_seconds": self.cadence_seconds,
            "first_timestamp_utc": self.first_timestamp_utc,
            "last_timestamp_utc": self.last_timestamp_utc,
            "time_axis_sha256": self.time_axis_sha256,
            "component_records": self.component_records,
            "shared_weather_driver_id": self.shared_weather_driver_id,
            "aligned_on_common_calendar": self.aligned_on_common_calendar,
            "congestion_evaluated": self.congestion_evaluated,
            "adequacy_certified": self.adequacy_certified,
            "manuscript_numbers_produced": self.manuscript_numbers_produced,
        }


def validate_canonical_calendar(timestamps: Sequence[datetime]) -> tuple[datetime, ...]:
    """Return validated 15-minute timezone-aware timestamps."""

    return _validate_time_axis(timestamps)


def component_calendar_footprint(
    *,
    component: str,
    timestamps: Sequence[datetime],
    member_id: str,
    source_id: str,
    shared_weather_driver_id: str | None = None,
) -> ComponentCalendarFootprint:
    """Build a UTC-normalized footprint without changing trajectory order."""

    return ComponentCalendarFootprint(
        component=component,
        member_id=member_id,
        source_id=source_id,
        timestamps_utc=tuple(_as_utc_timestamp(item) for item in timestamps),
        shared_weather_driver_id=shared_weather_driver_id,
    )


def validate_component_calendar_readiness(
    footprints: Sequence[ComponentCalendarFootprint],
    *,
    local_year: int,
    timezone: str = "Europe/Amsterdam",
    required_components: Sequence[str] = COMMON_CALENDAR_COMPONENTS,
) -> ComponentCalendarReadiness:
    """Validate the baseline/EV/HP/PV common-calendar handoff contract."""

    records = tuple(footprints)
    if not records:
        raise ValueError("At least one component calendar footprint is required")
    by_component: dict[str, ComponentCalendarFootprint] = {}
    for record in records:
        if record.component in by_component:
            raise ValueError("Component calendar footprints must have unique component names")
        by_component[record.component] = record
    missing = sorted(set(required_components) - set(by_component))
    if missing:
        raise ValueError(f"Missing required component calendar footprints: {missing}")

    canonical = _canonical_15min_utc_axis_for_local_year(local_year, timezone=timezone)
    for record in records:
        # ALEA-001 depends on exact shared instants; accepting merely equal
        # counts would let season/weekday relationships drift before Agent A.
        if record.timestamps_utc != canonical:
            raise ValueError(f"{record.component} does not match the canonical {local_year} calendar")

    hp_weather_id = by_component["hp"].shared_weather_driver_id
    pv_weather_id = by_component["pv"].shared_weather_driver_id
    if not hp_weather_id or not pv_weather_id:
        raise ValueError("HP and PV calendar footprints must record a shared_weather_driver_id")
    if hp_weather_id != pv_weather_id:
        raise ValueError("HP and PV must use the same shared_weather_driver_id")

    calendar_id = f"e2_s5_common_15min_{local_year}_{timezone}"
    return ComponentCalendarReadiness(
        calendar_id=calendar_id,
        local_year=local_year,
        timezone=timezone,
        n_timesteps=len(canonical),
        cadence_seconds=EXPECTED_STEP_SECONDS,
        first_timestamp_utc=canonical[0].isoformat(),
        last_timestamp_utc=canonical[-1].isoformat(),
        time_axis_sha256=_hash_json([item.isoformat() for item in canonical]),
        component_records=tuple(record.manifest_record() for record in records),
        shared_weather_driver_id=hp_weather_id,
    )


def _validate_time_axis(timestamps: Sequence[datetime]) -> tuple[datetime, ...]:
    normalized = tuple(timestamps)
    if not normalized:
        raise ValueError("Baseline timestamps must be non-empty")
    for item in normalized:
        if item.tzinfo is None or item.utcoffset() is None:
            raise ValueError("Baseline timestamps must be timezone-aware")
    if len(normalized) == 1:
        return normalized
    # Compare absolute instants so daylight-saving transitions do not create a
    # false 15-minute spacing failure on a local canonical calendar.
    deltas = np.diff([item.timestamp() for item in normalized])
    if not np.all(deltas == EXPECTED_STEP_SECONDS):
        raise ValueError("Baseline timestamps must be strictly 15-minute spaced")
    return normalized


def _validate_utc_time_axis(timestamps: Sequence[datetime]) -> tuple[datetime, ...]:
    normalized = tuple(_as_utc_timestamp(item) for item in timestamps)
    if not normalized:
        raise ValueError("Component timestamps must be non-empty")
    if len(normalized) == 1:
        return normalized
    deltas = np.diff([item.timestamp() for item in normalized])
    if not np.all(deltas == EXPECTED_STEP_SECONDS):
        raise ValueError("Component timestamps must be strictly 15-minute spaced")
    return normalized


def _as_utc_timestamp(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("timestamps entries must be datetimes")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC)


def _canonical_15min_utc_axis_for_local_year(
    year: int,
    *,
    timezone: str,
) -> tuple[datetime, ...]:
    local_zone = ZoneInfo(timezone)
    start_utc = datetime(int(year), 1, 1, tzinfo=local_zone).astimezone(UTC)
    end_utc = datetime(int(year) + 1, 1, 1, tzinfo=local_zone).astimezone(UTC)
    step = timedelta(seconds=EXPECTED_STEP_SECONDS)
    values: list[datetime] = []
    current = start_utc
    while current < end_utc:
        values.append(current)
        current += step
    if current != end_utc:
        raise AssertionError("15-minute axis did not land on local year boundary")
    return tuple(values)


def _validate_load_values(values: np.ndarray, n_timesteps: int) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim not in {1, 2}:
        raise ValueError("Baseline load values must be one- or two-dimensional")
    if array.shape[0] != n_timesteps:
        raise ValueError("Baseline load length must match timestamp count")
    if not np.isfinite(array).all():
        raise ValueError("Baseline load values must be finite")
    return np.ascontiguousarray(array)


def _hash_json(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _meteorological_season(month: int) -> str:
    if month in {12, 1, 2}:
        return "winter"
    if month in {3, 4, 5}:
        return "spring"
    if month in {6, 7, 8}:
        return "summer"
    return "autumn"


def _require_non_empty_string(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
