from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
from typing import Any

import numpy as np

from src.weather_model import (
    LOCAL_TIMEZONE,
    WeatherMember,
    canonical_15min_local_axis_for_year,
    canonical_15min_utc_axis_for_local_year,
    validate_canonical_15min_calendar,
)

SEASON_BY_MONTH = {
    12: "DJF",
    1: "DJF",
    2: "DJF",
    3: "MAM",
    4: "MAM",
    5: "MAM",
    6: "JJA",
    7: "JJA",
    8: "JJA",
    9: "SON",
    10: "SON",
    11: "SON",
}
SEASONS = ("DJF", "MAM", "JJA", "SON")

@dataclass(frozen=True)
class PVSystemConfig:
    """Explicit deterministic PV conversion parameters for one PV fleet."""

    installed_capacity_kw: float
    performance_ratio: float
    reference_irradiance_w_per_m2: float
    temperature_coefficient_per_c: float
    reference_temperature_c: float
    clip_to_capacity: bool
    config_id: str = "explicit"

    def __post_init__(self) -> None:
        if not self.config_id:
            raise ValueError("config_id must be non-empty")
        _require_positive_finite(self.installed_capacity_kw, "installed_capacity_kw")
        if not _is_finite(self.performance_ratio) or not 0 < self.performance_ratio <= 1.0:
            raise ValueError("performance_ratio must be finite and in (0, 1]")
        _require_positive_finite(self.reference_irradiance_w_per_m2, "reference_irradiance_w_per_m2")
        _require_finite(self.temperature_coefficient_per_c, "temperature_coefficient_per_c")
        _require_finite(self.reference_temperature_c, "reference_temperature_c")
        if not isinstance(self.clip_to_capacity, bool):
            raise ValueError("clip_to_capacity must be a bool")


@dataclass(frozen=True)
class PVGenerationProfile:
    """PV generation produced from one validated paired weather member."""

    weather_member_id: str
    weather_source: str
    shared_weather_driver_id: str
    timestamps_utc: Sequence[datetime]
    timestamps_local: Sequence[datetime]
    generation_kw: Sequence[float]
    config: PVSystemConfig

    def __post_init__(self) -> None:
        timestamps_utc = tuple(_coerce_aware_datetime(item, "timestamps_utc").astimezone(UTC) for item in self.timestamps_utc)
        timestamps_local = tuple(_coerce_aware_datetime(item, "timestamps_local") for item in self.timestamps_local)
        if len(timestamps_utc) < 2:
            raise ValueError("PV profile must contain at least two timestamps")
        if len(timestamps_utc) != len(timestamps_local):
            raise ValueError("UTC and local timestamp counts must match")
        _validate_strictly_chronological(timestamps_utc, "PV profile")
        for utc_timestamp, local_timestamp in zip(timestamps_utc, timestamps_local, strict=True):
            if local_timestamp.astimezone(UTC) != utc_timestamp:
                raise ValueError("UTC and local timestamps must represent the same instants")
        generation = _as_float_vector(self.generation_kw, "generation_kw")
        if len(generation) != len(timestamps_utc):
            raise ValueError("generation_kw must match the timestamp count")
        if (generation < 0).any():
            raise ValueError("generation_kw must be non-negative")

        object.__setattr__(self, "timestamps_utc", timestamps_utc)
        object.__setattr__(self, "timestamps_local", timestamps_local)
        object.__setattr__(self, "generation_kw", generation)

    @property
    def n_timesteps(self) -> int:
        return len(self.timestamps_utc)

    @property
    def cadence_seconds(self) -> int:
        return _constant_cadence_seconds(self.timestamps_utc)

    @property
    def cadence_hours(self) -> float:
        return self.cadence_seconds / 3600.0

    def annual_energy_kwh(self) -> float:
        return float(np.sum(self.generation_kw) * self.cadence_hours)

    def peak_kw(self) -> float:
        return float(np.max(self.generation_kw))

    def peak_timestamp_local(self) -> datetime:
        return self.timestamps_local[int(np.argmax(self.generation_kw))]


@dataclass(frozen=True)
class PVGISReference:
    """Seasonal PVGIS reference for calibration or validation, not sampling."""

    source_id: str
    seasonal_energy_kwh: Mapping[str, float]
    annual_energy_kwh: float | None = None
    peak_month: int | None = None
    typical_year_use: str = "calibration_or_validation_only"

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("source_id must be non-empty")
        seasonal = {season: float(self.seasonal_energy_kwh[season]) for season in SEASONS}
        for season, value in seasonal.items():
            if not _is_finite(value) or value < 0:
                raise ValueError(f"{season} reference energy must be finite and non-negative")
        annual = sum(seasonal.values()) if self.annual_energy_kwh is None else float(self.annual_energy_kwh)
        if not _is_finite(annual) or annual < 0:
            raise ValueError("annual_energy_kwh must be finite and non-negative")
        if self.peak_month is not None and int(self.peak_month) not in range(1, 13):
            raise ValueError("peak_month must be in 1..12")
        if self.typical_year_use != "calibration_or_validation_only":
            raise ValueError("PVGIS typical-year references must not be sampled as realized weather paths")

        object.__setattr__(self, "seasonal_energy_kwh", seasonal)
        object.__setattr__(self, "annual_energy_kwh", annual)
        object.__setattr__(self, "peak_month", None if self.peak_month is None else int(self.peak_month))


@dataclass(frozen=True)
class PVGISSanityCheck:
    """Result of a PV profile check against PVGIS seasonal/peak expectations."""

    passed: bool
    seasonal_relative_error: Mapping[str, float]
    annual_relative_error: float
    profile_peak_month: int
    peak_timing_passed: bool
    failed_reasons: tuple[str, ...]

    def raise_for_failure(self) -> None:
        if not self.passed:
            raise ValueError("; ".join(self.failed_reasons))
def generate_pv_profile(weather: WeatherMember, config: PVSystemConfig) -> PVGenerationProfile:
    """Generate PV power in kW from paired irradiance and temperature channels."""
    temperature_factor = 1.0 + config.temperature_coefficient_per_c * (
        weather.temperature_c - config.reference_temperature_c
    )
    # Extreme temperatures must reduce output to zero at worst; otherwise a
    # pathological coefficient/input pair could silently turn PV into demand.
    temperature_factor = np.maximum(temperature_factor, 0.0)
    generation_kw = (
        config.installed_capacity_kw
        * config.performance_ratio
        * (weather.ghi_w_per_m2 / config.reference_irradiance_w_per_m2)
        * temperature_factor
    )
    generation_kw = np.maximum(generation_kw, 0.0)
    if config.clip_to_capacity:
        generation_kw = np.minimum(generation_kw, config.installed_capacity_kw)
    return PVGenerationProfile(
        weather_member_id=weather.member_id,
        weather_source=weather.source,
        shared_weather_driver_id=weather.shared_weather_driver_id,
        timestamps_utc=weather.timestamps_utc,
        timestamps_local=weather.timestamps_local,
        generation_kw=generation_kw.astype(np.float64),
        config=config,
    )


def seasonal_energy_kwh(profile: PVGenerationProfile) -> dict[str, float]:
    """Return PV energy by meteorological season using local timestamps."""
    totals = dict.fromkeys(SEASONS, 0.0)
    cadence_hours = profile.cadence_hours
    for value_kw, timestamp in zip(profile.generation_kw, profile.timestamps_local, strict=True):
        season = SEASON_BY_MONTH[timestamp.month]
        totals[season] += float(value_kw) * cadence_hours
    return {season: float(totals[season]) for season in SEASONS}


def summarize_pv_profile(profile: PVGenerationProfile) -> dict[str, object]:
    """Return commit-safe PV profile summary statistics."""
    peak_timestamp = profile.peak_timestamp_local()
    return {
        "weather_member_id": profile.weather_member_id,
        "weather_source": profile.weather_source,
        "shared_weather_driver_id": profile.shared_weather_driver_id,
        "n_timesteps": profile.n_timesteps,
        "cadence_seconds": profile.cadence_seconds,
        "annual_energy_kwh": profile.annual_energy_kwh(),
        "seasonal_energy_kwh": seasonal_energy_kwh(profile),
        "peak_kw": profile.peak_kw(),
        "peak_timestamp_local": peak_timestamp.isoformat(),
        "peak_month": peak_timestamp.month,
        "config_id": profile.config.config_id,
    }


def check_profile_against_pvgis_reference(
    profile: PVGenerationProfile,
    reference: PVGISReference,
    *,
    max_relative_seasonal_error: float,
    max_relative_annual_error: float | None = None,
    allowed_peak_months: Sequence[int] | None = None,
) -> PVGISSanityCheck:
    """Compare seasonal totals and peak timing against a PVGIS reference."""
    if max_relative_seasonal_error < 0:
        raise ValueError("max_relative_seasonal_error must be non-negative")
    if max_relative_annual_error is not None and max_relative_annual_error < 0:
        raise ValueError("max_relative_annual_error must be non-negative")

    profile_seasonal = seasonal_energy_kwh(profile)
    relative_by_season = {
        season: _relative_error(profile_seasonal[season], reference.seasonal_energy_kwh[season])
        for season in SEASONS
    }
    failed: list[str] = [
        f"{season} seasonal relative error {relative_by_season[season]:.6g} exceeds {max_relative_seasonal_error:.6g}"
        for season in SEASONS
        if relative_by_season[season] > max_relative_seasonal_error
    ]
    annual_error = _relative_error(profile.annual_energy_kwh(), reference.annual_energy_kwh)
    if max_relative_annual_error is not None and annual_error > max_relative_annual_error:
        failed.append(f"annual relative error {annual_error:.6g} exceeds {max_relative_annual_error:.6g}")

    peak_month = profile.peak_timestamp_local().month
    allowed_months = _allowed_peak_months(reference, allowed_peak_months)
    peak_timing_passed = True
    if allowed_months:
        peak_timing_passed = peak_month in allowed_months
        if not peak_timing_passed:
            failed.append(f"peak month {peak_month} outside allowed PVGIS months {sorted(allowed_months)}")

    return PVGISSanityCheck(
        passed=not failed,
        seasonal_relative_error=relative_by_season,
        annual_relative_error=annual_error,
        profile_peak_month=peak_month,
        peak_timing_passed=peak_timing_passed,
        failed_reasons=tuple(failed),
    )


def parse_pvgis_monthly_reference(
    payload: bytes | str | Mapping[str, Any],
    *,
    source_id: str,
) -> PVGISReference:
    """Parse PVGIS monthly JSON into a seasonal reference object."""
    if isinstance(payload, bytes):
        parsed = json.loads(payload.decode("utf-8"))
    elif isinstance(payload, str):
        parsed = json.loads(payload)
    else:
        parsed = dict(payload)
    outputs = parsed.get("outputs")
    if not isinstance(outputs, Mapping):
        raise ValueError("PVGIS payload lacks outputs")
    monthly = outputs.get("monthly")
    if isinstance(monthly, Mapping):
        rows = monthly.get("fixed") or monthly.get("monthly")
    else:
        rows = monthly
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ValueError("PVGIS monthly output lacks a row sequence")

    by_month: dict[int, float] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("PVGIS monthly row must be an object")
        month = int(row["month"])
        if month not in range(1, 13):
            raise ValueError("PVGIS monthly row has invalid month")
        if "E_m" in row:
            energy = float(row["E_m"])
        elif "E" in row:
            energy = float(row["E"])
        else:
            raise ValueError("PVGIS monthly row lacks E_m or E")
        if not _is_finite(energy) or energy < 0:
            raise ValueError("PVGIS monthly energy must be finite and non-negative")
        by_month[month] = energy
    if set(by_month) != set(range(1, 13)):
        raise ValueError("PVGIS monthly output must contain all 12 months")

    seasonal = dict.fromkeys(SEASONS, 0.0)
    for month, energy in by_month.items():
        seasonal[SEASON_BY_MONTH[month]] += energy
    peak_month = max(by_month, key=lambda month: by_month[month])
    return PVGISReference(
        source_id=source_id,
        seasonal_energy_kwh=seasonal,
        annual_energy_kwh=sum(by_month.values()),
        peak_month=peak_month,
    )


def _coerce_aware_datetime(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{name} entries must be datetimes")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} entries must be timezone-aware")
    return value


def _validate_strictly_chronological(values: Sequence[datetime], label: str) -> None:
    for previous, current in zip(values, values[1:]):
        if current <= previous:
            raise ValueError(f"{label} timestamps must be complete and chronological")


def _constant_cadence_seconds(values: Sequence[datetime]) -> int:
    deltas = {int((current - previous).total_seconds()) for previous, current in zip(values, values[1:])}
    if len(deltas) != 1:
        raise ValueError("Timestamps must have one constant cadence")
    cadence = deltas.pop()
    if cadence <= 0:
        raise ValueError("Timestamp cadence must be positive")
    return cadence


def _as_float_vector(values: Sequence[float], name: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1:
        raise ValueError(f"{name} must be a one-dimensional vector")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} contains missing or non-finite values")
    copied = array.astype(np.float64, copy=True)
    copied.setflags(write=False)
    return copied


def _require_positive_finite(value: float, name: str) -> None:
    _require_finite(value, name)
    if float(value) <= 0:
        raise ValueError(f"{name} must be positive")


def _require_finite(value: float, name: str) -> None:
    if not _is_finite(float(value)):
        raise ValueError(f"{name} must be finite")


def _is_finite(value: float | None) -> bool:
    return value is not None and np.isfinite(float(value))


def _relative_error(actual: float, expected: float) -> float:
    actual_float = float(actual)
    expected_float = float(expected)
    if expected_float == 0:
        return 0.0 if actual_float == 0 else float("inf")
    return abs(actual_float - expected_float) / abs(expected_float)


def _allowed_peak_months(
    reference: PVGISReference,
    allowed_peak_months: Sequence[int] | None,
) -> set[int]:
    if allowed_peak_months is not None:
        months = {int(month) for month in allowed_peak_months}
    elif reference.peak_month is not None:
        months = {reference.peak_month}
    else:
        months = set()
    invalid = sorted(month for month in months if month not in range(1, 13))
    if invalid:
        raise ValueError(f"allowed_peak_months contains invalid months: {invalid}")
    return months
