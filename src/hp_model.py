"""Heat-pump profile support for E2.S3.

The module consumes externally selected weather/calendar members. It does not
sample weather, retrieve KNMI/PVGIS data, or aggregate net load.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd


HOURLY_STEP_MINUTES = 60
QUARTER_HOUR_STEP_MINUTES = 15
QUARTER_HOURS_PER_HOUR = HOURLY_STEP_MINUTES // QUARTER_HOUR_STEP_MINUTES


@dataclass(frozen=True)
class WeatherMember:
    """Aligned weather member supplied by the future shared weather layer.

    Parameters
    ----------
    member_id:
        Traceable identifier for the paired weather realization.
    timestamps_utc:
        Timezone-aware UTC timestamps at 15-minute resolution.
    temperature_c:
        Outdoor dry-bulb temperature in degrees Celsius aligned to
        ``timestamps_utc``.
    source:
        Human-readable source label; this module does not interpret it as a
        sampling rule.
    """

    member_id: str
    timestamps_utc: tuple[datetime, ...]
    temperature_c: np.ndarray
    source: str = "shared_weather_layer"

    def __post_init__(self) -> None:
        timestamps = tuple(_as_utc_timestamp(item) for item in self.timestamps_utc)
        temperature = np.asarray(self.temperature_c, dtype=np.float64)
        if len(timestamps) != temperature.shape[0]:
            raise ValueError("weather timestamps and temperature_c must have the same length")
        if not self.member_id:
            raise ValueError("weather member_id must be non-empty")
        if not np.isfinite(temperature).all():
            raise ValueError("temperature_c must contain only finite values")
        _validate_regular_step(timestamps, QUARTER_HOUR_STEP_MINUTES, label="weather")
        object.__setattr__(self, "timestamps_utc", timestamps)
        object.__setattr__(self, "temperature_c", temperature)


@dataclass(frozen=True)
class When2HeatComponent:
    """One thermal-demand column and its matching COP column.

    Parameters
    ----------
    heat_column:
        When2Heat heat-demand or heat-profile column. Normalized
        ``heat_profile`` columns are interpreted as MW per annual TWh.
    cop_column:
        When2Heat COP column used to convert this component's thermal demand
        into electric demand.
    annual_heat_demand_twh:
        Explicit thermal-energy scale in TWh/year for normalized
        ``heat_profile`` columns. Use ``1.0`` only for the source's unit
        profile, not as an adoption assumption.
    """

    heat_column: str
    cop_column: str
    annual_heat_demand_twh: float

    def __post_init__(self) -> None:
        if not self.heat_column or not self.cop_column:
            raise ValueError("When2Heat component columns must be non-empty")
        if self.annual_heat_demand_twh <= 0:
            raise ValueError("annual_heat_demand_twh must be positive")


@dataclass(frozen=True)
class When2HeatHourlyProfile:
    """Hourly thermal and electric heat-pump demand from When2Heat.

    Demand arrays are average power in kW for each source hour.
    """

    timestamps_utc: tuple[datetime, ...]
    thermal_demand_kw: np.ndarray
    electric_kw: np.ndarray
    cop: np.ndarray
    components: tuple[When2HeatComponent, ...]
    source_path: str | None = None

    def __post_init__(self) -> None:
        timestamps = tuple(_as_utc_timestamp(item) for item in self.timestamps_utc)
        thermal = np.asarray(self.thermal_demand_kw, dtype=np.float64)
        electric = np.asarray(self.electric_kw, dtype=np.float64)
        cop = np.asarray(self.cop, dtype=np.float64)
        _validate_profile_arrays(timestamps, thermal, electric, cop, step_minutes=HOURLY_STEP_MINUTES)
        object.__setattr__(self, "timestamps_utc", timestamps)
        object.__setattr__(self, "thermal_demand_kw", thermal)
        object.__setattr__(self, "electric_kw", electric)
        object.__setattr__(self, "cop", cop)


@dataclass(frozen=True)
class When2HeatQuarterHourProfile:
    """15-minute heat-pump demand after explicit hourly downscaling."""

    timestamps_utc: tuple[datetime, ...]
    thermal_demand_kw: np.ndarray
    electric_kw: np.ndarray
    cop: np.ndarray
    components: tuple[When2HeatComponent, ...]
    source_path: str | None
    downscaling_method: str

    def __post_init__(self) -> None:
        timestamps = tuple(_as_utc_timestamp(item) for item in self.timestamps_utc)
        thermal = np.asarray(self.thermal_demand_kw, dtype=np.float64)
        electric = np.asarray(self.electric_kw, dtype=np.float64)
        cop = np.asarray(self.cop, dtype=np.float64)
        _validate_profile_arrays(
            timestamps,
            thermal,
            electric,
            cop,
            step_minutes=QUARTER_HOUR_STEP_MINUTES,
        )
        object.__setattr__(self, "timestamps_utc", timestamps)
        object.__setattr__(self, "thermal_demand_kw", thermal)
        object.__setattr__(self, "electric_kw", electric)
        object.__setattr__(self, "cop", cop)


@dataclass(frozen=True)
class HeatPumpProfile:
    """Heat-pump electric demand aligned to one shared weather member."""

    weather_member_id: str
    timestamps_utc: tuple[datetime, ...]
    electric_kw: np.ndarray
    thermal_demand_kw: np.ndarray
    cop: np.ndarray
    temperature_c: np.ndarray
    source_columns: tuple[str, ...]
    source_path: str | None
    downscaling_method: str

    def __post_init__(self) -> None:
        timestamps = tuple(_as_utc_timestamp(item) for item in self.timestamps_utc)
        electric = np.asarray(self.electric_kw, dtype=np.float64)
        thermal = np.asarray(self.thermal_demand_kw, dtype=np.float64)
        cop = np.asarray(self.cop, dtype=np.float64)
        temperature = np.asarray(self.temperature_c, dtype=np.float64)
        _validate_profile_arrays(
            timestamps,
            thermal,
            electric,
            cop,
            step_minutes=QUARTER_HOUR_STEP_MINUTES,
        )
        if temperature.shape != electric.shape:
            raise ValueError("temperature_c must align with heat-pump demand")
        if not np.isfinite(temperature).all():
            raise ValueError("temperature_c must contain only finite values")
        object.__setattr__(self, "timestamps_utc", timestamps)
        object.__setattr__(self, "electric_kw", electric)
        object.__setattr__(self, "thermal_demand_kw", thermal)
        object.__setattr__(self, "cop", cop)
        object.__setattr__(self, "temperature_c", temperature)


@dataclass(frozen=True)
class ColdWeekSanity:
    """Diagnostic linking heat-pump peak demand to the coldest calendar week."""

    peak_timestamp_utc: datetime
    peak_load_kw: float
    peak_temperature_c: float
    coldest_week_start_utc: datetime
    coldest_week_end_utc: datetime
    coldest_week_mean_temperature_c: float
    max_load_inside_cold_week_kw: float
    max_load_outside_cold_week_kw: float
    peak_inside_cold_week: bool


def default_when2heat_components(
    *,
    country_code: str = "NL",
    space_heat_twh_by_class: Mapping[str, float] | None = None,
    water_heat_twh_by_class: Mapping[str, float] | None = None,
    heat_pump_source: str = "ASHP",
    space_sink: str = "radiator",
) -> tuple[When2HeatComponent, ...]:
    """Build explicit NL-style When2Heat component mappings.

    The mapping values are scales for normalized source profiles; they are not
    adoption counts or scenario defaults.
    """
    if not space_heat_twh_by_class and not water_heat_twh_by_class:
        raise ValueError("At least one explicit annual heat TWh scale is required")
    country = country_code.upper()
    source = heat_pump_source.upper()
    components: list[When2HeatComponent] = []
    for building_class, annual_heat_twh in (space_heat_twh_by_class or {}).items():
        components.append(
            When2HeatComponent(
                heat_column=f"{country}_heat_profile_space_{building_class}",
                cop_column=f"{country}_COP_{source}_{space_sink}",
                annual_heat_demand_twh=float(annual_heat_twh),
            )
        )
    for building_class, annual_heat_twh in (water_heat_twh_by_class or {}).items():
        components.append(
            When2HeatComponent(
                heat_column=f"{country}_heat_profile_water_{building_class}",
                cop_column=f"{country}_COP_{source}_water",
                annual_heat_demand_twh=float(annual_heat_twh),
            )
        )
    return tuple(components)


def load_when2heat_hourly_csv(
    path: str | Path,
    *,
    components: Sequence[When2HeatComponent],
    timestamp_column: str = "utc_timestamp",
) -> When2HeatHourlyProfile:
    """Load selected When2Heat components from the single-index hourly CSV.

    Thermal profile columns are interpreted as average MW per normalized annual
    TWh and converted to kW before component-wise division by COP.
    """
    if not components:
        raise ValueError("At least one When2Heat component is required")
    source_path = Path(path)
    frame = pd.read_csv(source_path)
    if timestamp_column not in frame.columns:
        raise ValueError(f"When2Heat CSV lacks timestamp column {timestamp_column!r}")

    timestamps = tuple(_parse_utc_timestamp(value) for value in frame[timestamp_column])
    total_thermal_kw = np.zeros(len(frame), dtype=np.float64)
    total_electric_kw = np.zeros(len(frame), dtype=np.float64)
    cop_stack: list[np.ndarray] = []
    missing_columns = [
        column
        for component in components
        for column in (component.heat_column, component.cop_column)
        if column not in frame.columns
    ]
    if missing_columns:
        raise ValueError(f"When2Heat CSV lacks required columns: {sorted(set(missing_columns))}")

    for component in components:
        thermal_kw = (
            frame[component.heat_column].to_numpy(dtype=np.float64)
            * component.annual_heat_demand_twh
            * 1000.0
        )
        cop = frame[component.cop_column].to_numpy(dtype=np.float64)
        if (thermal_kw < 0).any():
            raise ValueError(f"{component.heat_column} contains negative thermal demand")
        if not np.isfinite(cop).all() or (cop <= 0).any():
            raise ValueError(f"{component.cop_column} must contain positive finite COP values")
        total_thermal_kw += thermal_kw
        total_electric_kw += thermal_kw / cop
        cop_stack.append(cop)

    fallback_cop = np.mean(np.vstack(cop_stack), axis=0)
    equivalent_cop = np.divide(
        total_thermal_kw,
        total_electric_kw,
        out=fallback_cop.copy(),
        where=total_electric_kw > 0,
    )
    return When2HeatHourlyProfile(
        timestamps_utc=timestamps,
        thermal_demand_kw=total_thermal_kw,
        electric_kw=total_electric_kw,
        cop=equivalent_cop,
        components=tuple(components),
        source_path=source_path.as_posix(),
    )


def downscale_hourly_to_15min(hourly: When2HeatHourlyProfile) -> When2HeatQuarterHourProfile:
    """Convert hourly average-power values to 15-minute average-power values.

    The downscaling is a zero-order hold: each source hour is copied into four
    quarter-hour intervals. This preserves energy exactly because the source
    and target arrays both represent average power over their intervals.
    """
    timestamps: list[datetime] = []
    for timestamp in hourly.timestamps_utc:
        timestamps.extend(
            timestamp + timedelta(minutes=QUARTER_HOUR_STEP_MINUTES * offset)
            for offset in range(QUARTER_HOURS_PER_HOUR)
        )
    return When2HeatQuarterHourProfile(
        timestamps_utc=tuple(timestamps),
        thermal_demand_kw=np.repeat(hourly.thermal_demand_kw, QUARTER_HOURS_PER_HOUR),
        electric_kw=np.repeat(hourly.electric_kw, QUARTER_HOURS_PER_HOUR),
        cop=np.repeat(hourly.cop, QUARTER_HOURS_PER_HOUR),
        components=hourly.components,
        source_path=hourly.source_path,
        downscaling_method="hourly_zero_order_hold_to_15min_energy_preserving",
    )


def align_heat_pump_profile(
    when2heat_15min: When2HeatQuarterHourProfile,
    weather: WeatherMember,
) -> HeatPumpProfile:
    """Attach a 15-minute When2Heat profile to one supplied weather member."""
    if when2heat_15min.timestamps_utc != weather.timestamps_utc:
        raise ValueError("When2Heat profile and weather member timestamps are not exactly aligned")
    source_columns = tuple(
        column
        for component in when2heat_15min.components
        for column in (component.heat_column, component.cop_column)
    )
    return HeatPumpProfile(
        weather_member_id=weather.member_id,
        timestamps_utc=when2heat_15min.timestamps_utc,
        electric_kw=when2heat_15min.electric_kw,
        thermal_demand_kw=when2heat_15min.thermal_demand_kw,
        cop=when2heat_15min.cop,
        temperature_c=weather.temperature_c,
        source_columns=source_columns,
        source_path=when2heat_15min.source_path,
        downscaling_method=when2heat_15min.downscaling_method,
    )


def build_heat_pump_profile_from_when2heat_csv(
    path: str | Path,
    *,
    weather: WeatherMember,
    components: Sequence[When2HeatComponent],
    timestamp_column: str = "utc_timestamp",
) -> HeatPumpProfile:
    """Load, downscale, and align a When2Heat profile to supplied weather."""
    hourly = load_when2heat_hourly_csv(
        path,
        components=components,
        timestamp_column=timestamp_column,
    )
    return align_heat_pump_profile(downscale_hourly_to_15min(hourly), weather)


def cold_week_sanity_check(profile: HeatPumpProfile, *, window_days: int = 7) -> ColdWeekSanity:
    """Check whether peak electric HP demand falls inside the coldest week."""
    if window_days <= 0:
        raise ValueError("window_days must be positive")
    steps_per_day = _steps_per_day(profile.timestamps_utc)
    window_steps = steps_per_day * window_days
    if len(profile.timestamps_utc) < window_steps:
        raise ValueError("profile is shorter than the requested cold-week window")

    rolling = np.convolve(
        profile.temperature_c,
        np.ones(window_steps, dtype=np.float64) / window_steps,
        mode="valid",
    )
    cold_start = int(np.argmin(rolling))
    cold_stop = cold_start + window_steps
    peak_load = float(np.max(profile.electric_kw))
    peak_indices = np.flatnonzero(np.isclose(profile.electric_kw, peak_load))
    inside_peak_indices = [index for index in peak_indices if cold_start <= index < cold_stop]
    peak_index = int(inside_peak_indices[0] if inside_peak_indices else peak_indices[0])
    outside_mask = np.ones_like(profile.electric_kw, dtype=bool)
    outside_mask[cold_start:cold_stop] = False
    outside_max = float(np.max(profile.electric_kw[outside_mask])) if outside_mask.any() else 0.0

    return ColdWeekSanity(
        peak_timestamp_utc=profile.timestamps_utc[peak_index],
        peak_load_kw=peak_load,
        peak_temperature_c=float(profile.temperature_c[peak_index]),
        coldest_week_start_utc=profile.timestamps_utc[cold_start],
        coldest_week_end_utc=profile.timestamps_utc[cold_stop - 1]
        + timedelta(minutes=QUARTER_HOUR_STEP_MINUTES),
        coldest_week_mean_temperature_c=float(rolling[cold_start]),
        max_load_inside_cold_week_kw=float(np.max(profile.electric_kw[cold_start:cold_stop])),
        max_load_outside_cold_week_kw=outside_max,
        peak_inside_cold_week=bool(inside_peak_indices),
    )


def _validate_profile_arrays(
    timestamps: Sequence[datetime],
    thermal_kw: np.ndarray,
    electric_kw: np.ndarray,
    cop: np.ndarray,
    *,
    step_minutes: int,
) -> None:
    if not timestamps:
        raise ValueError("profile timestamps cannot be empty")
    shape = (len(timestamps),)
    if thermal_kw.shape != shape or electric_kw.shape != shape or cop.shape != shape:
        raise ValueError("profile arrays must be one-dimensional and match timestamps")
    if not np.isfinite(thermal_kw).all() or not np.isfinite(electric_kw).all() or not np.isfinite(cop).all():
        raise ValueError("profile arrays must contain only finite values")
    if (thermal_kw < 0).any() or (electric_kw < 0).any():
        raise ValueError("heat-pump demand arrays must be non-negative")
    if (cop <= 0).any():
        raise ValueError("COP values must be positive")
    _validate_regular_step(timestamps, step_minutes, label="profile")


def _validate_regular_step(timestamps: Sequence[datetime], step_minutes: int, *, label: str) -> None:
    if not timestamps:
        raise ValueError(f"{label} timestamps cannot be empty")
    if len(timestamps) == 1:
        return
    expected_seconds = step_minutes * 60
    deltas = np.diff([item.timestamp() for item in timestamps])
    if not np.all(deltas == expected_seconds):
        raise ValueError(f"{label} timestamps are not spaced at {step_minutes}-minute intervals")


def _steps_per_day(timestamps: Sequence[datetime]) -> int:
    if len(timestamps) < 2:
        raise ValueError("cannot infer steps per day from fewer than two timestamps")
    step_seconds = (timestamps[1] - timestamps[0]).total_seconds()
    if step_seconds <= 0:
        raise ValueError("timestamps must be increasing")
    steps = 24 * 60 * 60 / step_seconds
    if int(steps) != steps:
        raise ValueError("profile timestep does not divide one day exactly")
    return int(steps)


def _parse_utc_timestamp(value: object) -> datetime:
    if isinstance(value, datetime):
        return _as_utc_timestamp(value)
    text = str(value)
    return _as_utc_timestamp(datetime.fromisoformat(text.replace("Z", "+00:00")))


def _as_utc_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC)
