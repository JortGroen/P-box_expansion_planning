"""Baseline load trajectory scaffold for complete-calendar aleatory samples."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Sequence

import numpy as np


EXPECTED_STEP_SECONDS = 15 * 60
BASELINE_COMPONENT = "baseline_load"


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


def validate_canonical_calendar(timestamps: Sequence[datetime]) -> tuple[datetime, ...]:
    """Return validated 15-minute timezone-aware timestamps."""

    return _validate_time_axis(timestamps)


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
