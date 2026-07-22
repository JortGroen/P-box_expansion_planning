"""Heat-pump profile support for E2.S3.

The module consumes the paired weather/PV member selected by the shared
weather layer. It does not sample weather, retrieve KNMI/PVGIS data, or
aggregate net load.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pandas as pd


HOURLY_STEP_MINUTES = 60
QUARTER_HOUR_STEP_MINUTES = 15
QUARTER_HOURS_PER_HOUR = HOURLY_STEP_MINUTES // QUARTER_HOUR_STEP_MINUTES
PV_WEATHER_FIELD_CANDIDATES = (
    "ghi_w_per_m2",
    "dni_w_per_m2",
    "dhi_w_per_m2",
    "poa_global_w_per_m2",
    "irradiance_w_per_m2",
)
WHEN2HEAT_CSV_SEPARATOR = ";"
WHEN2HEAT_CSV_DECIMAL = ","
WHEN2HEAT_UTC_TIMESTAMP_COLUMN = "utc_timestamp"
WHEN2HEAT_LOCAL_TIMESTAMP_COLUMN = "cet_cest_timestamp"
WHEN2HEAT_HEAT_DEMAND_UNIT = "MW"
WHEN2HEAT_HEAT_PROFILE_UNIT = "MW_per_annual_TWh"
WHEN2HEAT_COP_UNIT = "dimensionless"
HP001_COUNTRY_CODE = "NL"
HP001_SPACE_COP_COLUMN = "NL_COP_ASHP_radiator"
HP001_WATER_COP_COLUMN = "NL_COP_ASHP_water"
HP001_RESIDENTIAL_BUILDING_CLASSES = ("SFH", "MFH")
HP001_DECISION_ID = "HP-001"
HP001_DATA_ID = "D-003"


class SharedWeatherMember(Protocol):
    """Structural contract supplied by the paired weather/PV layer.

    HP consumes this shared weather object; it does not construct an
    independent temperature-only realization.
    """

    member_id: str
    source: str
    timestamps_utc: Sequence[datetime]
    temperature_c: Sequence[float]
    # The concrete shared contract may expose irradiance either through named
    # PV fields or a pv_weather_fields mapping; HP validates their presence so
    # a temperature-only member cannot masquerade as the paired realization.

    @property
    def shared_weather_driver_id(self) -> str: ...


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
    end_use:
        Heat end use represented by this component, for example ``"space"``
        or ``"water"``.
    building_class:
        Building class represented by this component, for example ``"SFH"``
        or ``"MFH"``.
    provenance:
        Auditable source/decision metadata for this component.
    """

    heat_column: str
    cop_column: str
    annual_heat_demand_twh: float
    end_use: str | None = None
    building_class: str | None = None
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.heat_column or not self.cop_column:
            raise ValueError("When2Heat component columns must be non-empty")
        if self.annual_heat_demand_twh <= 0:
            raise ValueError("annual_heat_demand_twh must be positive")
        if self.end_use is not None and not str(self.end_use).strip():
            raise ValueError("end_use must be non-empty when provided")
        if self.building_class is not None and not str(self.building_class).strip():
            raise ValueError("building_class must be non-empty when provided")
        object.__setattr__(
            self,
            "end_use",
            str(self.end_use).strip() if self.end_use is not None else None,
        )
        object.__setattr__(
            self,
            "building_class",
            str(self.building_class).strip() if self.building_class is not None else None,
        )
        object.__setattr__(
            self,
            "provenance",
            _as_provenance_mapping(self.provenance, "component provenance"),
        )

    def as_record(self) -> dict[str, object]:
        """Return JSON-serializable component metadata for audit reports."""
        return {
            "heat_column": self.heat_column,
            "cop_column": self.cop_column,
            "annual_heat_demand_twh": self.annual_heat_demand_twh,
            "end_use": self.end_use,
            "building_class": self.building_class,
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True)
class When2HeatCsvMetadata:
    """Auditable CSV dialect, unit, and column metadata for D-003."""

    source_path: str
    csv_separator: str
    decimal: str
    timestamp_column: str
    local_timestamp_column: str | None
    heat_demand_unit: str
    heat_profile_unit: str
    cop_unit: str
    selected_heat_columns: tuple[str, ...]
    selected_cop_columns: tuple[str, ...]
    selected_components: tuple[dict[str, object], ...]
    first_timestamp_utc: str | None
    last_timestamp_utc: str | None
    first_timestamp_local: str | None
    last_timestamp_local: str | None
    n_rows_loaded: int

    def as_record(self) -> dict[str, object]:
        """Return JSON-serializable source metadata for audit reports."""
        return {
            "source_path": self.source_path,
            "csv_separator": self.csv_separator,
            "decimal": self.decimal,
            "timestamp_column": self.timestamp_column,
            "local_timestamp_column": self.local_timestamp_column,
            "heat_demand_unit": self.heat_demand_unit,
            "heat_profile_unit": self.heat_profile_unit,
            "cop_unit": self.cop_unit,
            "selected_heat_columns": self.selected_heat_columns,
            "selected_cop_columns": self.selected_cop_columns,
            "selected_components": self.selected_components,
            "first_timestamp_utc": self.first_timestamp_utc,
            "last_timestamp_utc": self.last_timestamp_utc,
            "first_timestamp_local": self.first_timestamp_local,
            "last_timestamp_local": self.last_timestamp_local,
            "n_rows_loaded": self.n_rows_loaded,
        }


@dataclass(frozen=True)
class HeatPumpComponentSeries:
    """One traceable HP-001 component before aggregation."""

    heat_column: str
    cop_column: str
    annual_heat_demand_twh: float
    end_use: str | None
    building_class: str | None
    thermal_demand_kw: np.ndarray
    electric_kw: np.ndarray
    cop: np.ndarray
    interval_hours: float = 1.0
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        thermal = np.asarray(self.thermal_demand_kw, dtype=np.float64)
        electric = np.asarray(self.electric_kw, dtype=np.float64)
        cop = np.asarray(self.cop, dtype=np.float64)
        if thermal.ndim != 1 or electric.shape != thermal.shape or cop.shape != thermal.shape:
            raise ValueError("component series arrays must be one-dimensional and aligned")
        if not np.isfinite(thermal).all() or not np.isfinite(electric).all() or not np.isfinite(cop).all():
            raise ValueError("component series arrays must contain only finite values")
        if (thermal < 0).any() or (electric < 0).any():
            raise ValueError("component demand arrays must be non-negative")
        if (cop <= 0).any():
            raise ValueError("component COP values must be positive")
        if self.interval_hours <= 0:
            raise ValueError("component interval_hours must be positive")
        object.__setattr__(self, "thermal_demand_kw", thermal)
        object.__setattr__(self, "electric_kw", electric)
        object.__setattr__(self, "cop", cop)
        object.__setattr__(self, "provenance", _as_provenance_mapping(self.provenance, "component provenance"))

    @property
    def component_id(self) -> str:
        building = self.building_class or "unknown_class"
        end_use = self.end_use or "unknown_end_use"
        return f"{building.lower()}_{end_use}"

    def metadata_record(self) -> dict[str, object]:
        """Return component-level metadata without embedding full arrays."""
        return {
            "component_id": self.component_id,
            "heat_column": self.heat_column,
            "cop_column": self.cop_column,
            "annual_heat_demand_twh": self.annual_heat_demand_twh,
            "end_use": self.end_use,
            "building_class": self.building_class,
            "n_timesteps": int(self.electric_kw.size),
            "interval_hours": self.interval_hours,
            "thermal_energy_kwh": float(self.thermal_demand_kw.sum() * self.interval_hours),
            "electric_energy_kwh": float(self.electric_kw.sum() * self.interval_hours),
            "provenance": dict(self.provenance),
        }


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
    component_series: tuple[HeatPumpComponentSeries, ...] = ()
    source_path: str | None = None
    source_metadata: When2HeatCsvMetadata | None = None

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
        _validate_component_series(self.component_series, expected_shape=electric.shape)


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
    component_series: tuple[HeatPumpComponentSeries, ...] = ()
    source_metadata: When2HeatCsvMetadata | None = None

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
        _validate_component_series(self.component_series, expected_shape=electric.shape)


@dataclass(frozen=True)
class HeatPumpProfile:
    """Heat-pump electric demand aligned to one shared weather member."""

    shared_weather_driver_id: str
    weather_member_id: str
    weather_source: str
    timestamps_utc: tuple[datetime, ...]
    electric_kw: np.ndarray
    thermal_demand_kw: np.ndarray
    cop: np.ndarray
    temperature_c: np.ndarray
    source_columns: tuple[str, ...]
    source_path: str | None
    downscaling_method: str
    pv_weather_field_names: tuple[str, ...]
    timestamps_local: tuple[datetime, ...] | None = None
    component_series: tuple[HeatPumpComponentSeries, ...] = ()
    weather_content_sha256: str | None = None
    weather_provenance: Mapping[str, Any] = field(default_factory=dict)
    source_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.shared_weather_driver_id:
            raise ValueError("shared_weather_driver_id must be non-empty")
        if not self.weather_member_id:
            raise ValueError("weather_member_id must be non-empty")
        if not self.weather_source:
            raise ValueError("weather_source must be non-empty")
        timestamps = tuple(_as_utc_timestamp(item) for item in self.timestamps_utc)
        timestamps_local = _coerce_optional_local_timestamps(self.timestamps_local, timestamps)
        electric = np.asarray(self.electric_kw, dtype=np.float64)
        thermal = np.asarray(self.thermal_demand_kw, dtype=np.float64)
        cop = np.asarray(self.cop, dtype=np.float64)
        temperature = np.asarray(self.temperature_c, dtype=np.float64)
        pv_weather_field_names = _coerce_field_names(self.pv_weather_field_names, "pv_weather_field_names")
        provenance = _as_provenance_mapping(self.weather_provenance, "weather_provenance")
        source_metadata = _as_provenance_mapping(self.source_metadata, "source_metadata")
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
        _validate_component_series(self.component_series, expected_shape=electric.shape)
        content_hash = _optional_text(self.weather_content_sha256, "weather_content_sha256")
        object.__setattr__(self, "timestamps_utc", timestamps)
        object.__setattr__(self, "electric_kw", electric)
        object.__setattr__(self, "thermal_demand_kw", thermal)
        object.__setattr__(self, "cop", cop)
        object.__setattr__(self, "temperature_c", temperature)
        object.__setattr__(self, "pv_weather_field_names", pv_weather_field_names)
        object.__setattr__(self, "timestamps_local", timestamps_local)
        object.__setattr__(self, "weather_content_sha256", content_hash)
        object.__setattr__(self, "weather_provenance", provenance)
        object.__setattr__(self, "source_metadata", source_metadata)

    @property
    def n_timesteps(self) -> int:
        return len(self.timestamps_utc)

    @property
    def cadence_seconds(self) -> int:
        if len(self.timestamps_utc) < 2:
            return 0
        return int((self.timestamps_utc[1] - self.timestamps_utc[0]).total_seconds())

    def weather_identity_record(self) -> dict[str, object]:
        """Return an auditable record for HP/PV shared-weather comparison."""
        record: dict[str, object] = {
            "shared_weather_driver_id": self.shared_weather_driver_id,
            "member_id": self.weather_member_id,
            "source": self.weather_source,
            "first_timestamp_utc": self.timestamps_utc[0].isoformat(),
            "last_timestamp_utc": self.timestamps_utc[-1].isoformat(),
            "n_timesteps": self.n_timesteps,
            "cadence_seconds": self.cadence_seconds,
            "pv_weather_field_names": self.pv_weather_field_names,
            "provenance": dict(self.weather_provenance),
        }
        if self.weather_content_sha256 is not None:
            record["content_sha256"] = self.weather_content_sha256
        if self.source_metadata:
            record["when2heat_source"] = dict(self.source_metadata)
        if self.timestamps_local is not None:
            record.update(
                {
                    "first_timestamp_local": self.timestamps_local[0].isoformat(),
                    "last_timestamp_local": self.timestamps_local[-1].isoformat(),
                }
            )
        return record

    def component_traceability_record(self) -> tuple[dict[str, object], ...]:
        """Return HP component records that remain auditable before aggregation."""
        return tuple(component.metadata_record() for component in self.component_series)


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
                end_use="space",
                building_class=str(building_class),
            )
        )
    for building_class, annual_heat_twh in (water_heat_twh_by_class or {}).items():
        components.append(
            When2HeatComponent(
                heat_column=f"{country}_heat_profile_water_{building_class}",
                cop_column=f"{country}_COP_{source}_water",
                annual_heat_demand_twh=float(annual_heat_twh),
                end_use="water",
                building_class=str(building_class),
            )
        )
    return tuple(components)


def hp001_residential_when2heat_components(
    *,
    space_heat_twh_by_class: Mapping[str, float],
    water_heat_twh_by_class: Mapping[str, float],
    provenance: Mapping[str, Any] | None = None,
) -> tuple[When2HeatComponent, ...]:
    """Build the HP-001 approved residential SFH/MFH space+DHW components.

    Annual TWh values remain caller-supplied because HP-001 approves D-003
    shape/COP use only; it does not approve local annual HP scaling.
    """
    _require_exact_hp001_classes(space_heat_twh_by_class, label="space_heat_twh_by_class")
    _require_exact_hp001_classes(water_heat_twh_by_class, label="water_heat_twh_by_class")
    base_provenance = {
        "decision_id": HP001_DECISION_ID,
        "data_id": HP001_DATA_ID,
        "source": "OPSD When2Heat 2023-07-27 when2heat.csv",
        "boundary": "residential_space_plus_domestic_hot_water",
        "annual_scaling_status": "caller_supplied_not_approved_by_hp001",
    }
    if provenance is not None:
        base_provenance.update(_as_provenance_mapping(provenance, "component provenance"))

    components: list[When2HeatComponent] = []
    for building_class in HP001_RESIDENTIAL_BUILDING_CLASSES:
        components.append(
            When2HeatComponent(
                heat_column=f"{HP001_COUNTRY_CODE}_heat_profile_space_{building_class}",
                cop_column=HP001_SPACE_COP_COLUMN,
                annual_heat_demand_twh=float(space_heat_twh_by_class[building_class]),
                end_use="space",
                building_class=building_class,
                provenance={
                    **base_provenance,
                    "component_boundary": f"{building_class}_space_heat",
                },
            )
        )
    for building_class in HP001_RESIDENTIAL_BUILDING_CLASSES:
        components.append(
            When2HeatComponent(
                heat_column=f"{HP001_COUNTRY_CODE}_heat_profile_water_{building_class}",
                cop_column=HP001_WATER_COP_COLUMN,
                annual_heat_demand_twh=float(water_heat_twh_by_class[building_class]),
                end_use="water",
                building_class=building_class,
                provenance={
                    **base_provenance,
                    "component_boundary": f"{building_class}_domestic_hot_water",
                },
            )
        )
    return tuple(components)


def load_when2heat_hourly_csv(
    path: str | Path,
    *,
    components: Sequence[When2HeatComponent],
    timestamp_column: str = WHEN2HEAT_UTC_TIMESTAMP_COLUMN,
    local_timestamp_column: str | None = WHEN2HEAT_LOCAL_TIMESTAMP_COLUMN,
    csv_separator: str = WHEN2HEAT_CSV_SEPARATOR,
    decimal: str = WHEN2HEAT_CSV_DECIMAL,
    nrows: int | None = None,
) -> When2HeatHourlyProfile:
    """Load selected When2Heat components from the single-index hourly CSV.

    Thermal profile columns are interpreted as average MW per normalized annual
    TWh and converted to kW before component-wise division by COP.
    """
    if not components:
        raise ValueError("At least one When2Heat component is required")
    source_path = Path(path)
    if len(csv_separator) != 1:
        raise ValueError("csv_separator must be exactly one character")
    if len(decimal) != 1:
        raise ValueError("decimal must be exactly one character")
    if nrows is not None and nrows <= 0:
        raise ValueError("nrows must be positive when provided")
    use_columns = _when2heat_use_columns(
        components,
        timestamp_column=timestamp_column,
        local_timestamp_column=local_timestamp_column,
    )
    # The OPSD 2023-07-27 single-index CSV is semicolon-delimited with comma
    # decimals; using the explicit dialect prevents silent one-column parsing.
    frame = pd.read_csv(
        source_path,
        sep=csv_separator,
        decimal=decimal,
        usecols=lambda column: column in use_columns,
        nrows=nrows,
    )
    if timestamp_column not in frame.columns:
        raise ValueError(f"When2Heat CSV lacks timestamp column {timestamp_column!r}")
    if local_timestamp_column is not None and local_timestamp_column not in frame.columns:
        raise ValueError(f"When2Heat CSV lacks local timestamp column {local_timestamp_column!r}")

    timestamps = tuple(_parse_utc_timestamp(value) for value in frame[timestamp_column])
    total_thermal_kw = np.zeros(len(frame), dtype=np.float64)
    total_electric_kw = np.zeros(len(frame), dtype=np.float64)
    cop_stack: list[np.ndarray] = []
    component_series: list[HeatPumpComponentSeries] = []
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
        electric_kw = thermal_kw / cop
        total_thermal_kw += thermal_kw
        total_electric_kw += electric_kw
        cop_stack.append(cop)
        component_series.append(
            HeatPumpComponentSeries(
                heat_column=component.heat_column,
                cop_column=component.cop_column,
                annual_heat_demand_twh=component.annual_heat_demand_twh,
                end_use=component.end_use,
                building_class=component.building_class,
                thermal_demand_kw=thermal_kw,
                electric_kw=electric_kw,
                cop=cop,
                interval_hours=1.0,
                provenance=component.provenance,
            )
        )

    local_values = (
        tuple(str(value) for value in frame[local_timestamp_column])
        if local_timestamp_column is not None
        else ()
    )
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
        component_series=tuple(component_series),
        source_path=source_path.as_posix(),
        source_metadata=When2HeatCsvMetadata(
            source_path=source_path.as_posix(),
            csv_separator=csv_separator,
            decimal=decimal,
            timestamp_column=timestamp_column,
            local_timestamp_column=local_timestamp_column,
            heat_demand_unit=WHEN2HEAT_HEAT_DEMAND_UNIT,
            heat_profile_unit=WHEN2HEAT_HEAT_PROFILE_UNIT,
            cop_unit=WHEN2HEAT_COP_UNIT,
            selected_heat_columns=tuple(component.heat_column for component in components),
            selected_cop_columns=tuple(component.cop_column for component in components),
            selected_components=tuple(component.as_record() for component in components),
            first_timestamp_utc=timestamps[0].isoformat() if timestamps else None,
            last_timestamp_utc=timestamps[-1].isoformat() if timestamps else None,
            first_timestamp_local=local_values[0] if local_values else None,
            last_timestamp_local=local_values[-1] if local_values else None,
            n_rows_loaded=len(frame),
        ),
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
        component_series=tuple(_downscale_component_series(component) for component in hourly.component_series),
        source_metadata=hourly.source_metadata,
    )


def align_heat_pump_profile(
    when2heat_15min: When2HeatQuarterHourProfile,
    weather: SharedWeatherMember,
) -> HeatPumpProfile:
    """Attach a 15-minute When2Heat profile to one supplied weather member."""
    weather_timestamps = tuple(_as_utc_timestamp(item) for item in weather.timestamps_utc)
    if when2heat_15min.timestamps_utc != weather_timestamps:
        raise ValueError("When2Heat profile and weather member timestamps are not exactly aligned")
    weather_temperature = np.asarray(weather.temperature_c, dtype=np.float64)
    if weather_temperature.shape != when2heat_15min.electric_kw.shape:
        raise ValueError("weather temperature_c must align with heat-pump demand")
    if not np.isfinite(weather_temperature).all():
        raise ValueError("weather temperature_c must contain only finite values")
    _validate_regular_step(weather_timestamps, QUARTER_HOUR_STEP_MINUTES, label="weather")

    member_id = _required_text_attr(weather, "member_id")
    source = _required_text_attr(weather, "source")
    shared_driver_id = _required_text_attr(weather, "shared_weather_driver_id")
    pv_weather_field_names = _paired_pv_weather_field_names(
        weather,
        expected_shape=when2heat_15min.electric_kw.shape,
    )
    timestamps_local = _coerce_optional_local_timestamps(
        getattr(weather, "timestamps_local", None),
        weather_timestamps,
    )
    source_columns = tuple(
        column
        for component in when2heat_15min.components
        for column in (component.heat_column, component.cop_column)
    )
    return HeatPumpProfile(
        shared_weather_driver_id=shared_driver_id,
        weather_member_id=member_id,
        weather_source=source,
        timestamps_utc=when2heat_15min.timestamps_utc,
        electric_kw=when2heat_15min.electric_kw,
        thermal_demand_kw=when2heat_15min.thermal_demand_kw,
        cop=when2heat_15min.cop,
        temperature_c=weather_temperature,
        source_columns=source_columns,
        source_path=when2heat_15min.source_path,
        downscaling_method=when2heat_15min.downscaling_method,
        pv_weather_field_names=pv_weather_field_names,
        timestamps_local=timestamps_local,
        component_series=when2heat_15min.component_series,
        weather_content_sha256=_weather_content_hash(weather),
        weather_provenance=_weather_provenance(weather),
        source_metadata=(
            when2heat_15min.source_metadata.as_record()
            if when2heat_15min.source_metadata is not None
            else {}
        ),
    )


def build_heat_pump_profile_from_when2heat_csv(
    path: str | Path,
    *,
    weather: SharedWeatherMember,
    components: Sequence[When2HeatComponent],
    timestamp_column: str = WHEN2HEAT_UTC_TIMESTAMP_COLUMN,
    local_timestamp_column: str | None = WHEN2HEAT_LOCAL_TIMESTAMP_COLUMN,
    csv_separator: str = WHEN2HEAT_CSV_SEPARATOR,
    decimal: str = WHEN2HEAT_CSV_DECIMAL,
    nrows: int | None = None,
) -> HeatPumpProfile:
    """Load, downscale, and align a When2Heat profile to supplied weather."""
    hourly = load_when2heat_hourly_csv(
        path,
        components=components,
        timestamp_column=timestamp_column,
        local_timestamp_column=local_timestamp_column,
        csv_separator=csv_separator,
        decimal=decimal,
        nrows=nrows,
    )
    return align_heat_pump_profile(downscale_hourly_to_15min(hourly), weather)


def build_executable_hp001_profile_from_when2heat_csv(
    path: str | Path,
    *,
    weather: SharedWeatherMember,
    components: Sequence[When2HeatComponent],
    timestamp_column: str = WHEN2HEAT_UTC_TIMESTAMP_COLUMN,
    local_timestamp_column: str | None = WHEN2HEAT_LOCAL_TIMESTAMP_COLUMN,
    csv_separator: str = WHEN2HEAT_CSV_SEPARATOR,
    decimal: str = WHEN2HEAT_CSV_DECIMAL,
    nrows: int | None = None,
) -> HeatPumpProfile:
    """Build an executable HP-001 profile only from signed annual scales.

    This guard prevents reviewed shape/COP scaffolds from becoming integrated
    HP load inputs before the local annual TWh/adoption values are signed.
    """
    require_signed_annual_scaling(components)
    return build_heat_pump_profile_from_when2heat_csv(
        path,
        weather=weather,
        components=components,
        timestamp_column=timestamp_column,
        local_timestamp_column=local_timestamp_column,
        csv_separator=csv_separator,
        decimal=decimal,
        nrows=nrows,
    )


def require_signed_annual_scaling(components: Sequence[When2HeatComponent]) -> None:
    """Raise unless all HP components carry signed annual-scaling provenance."""
    if not components:
        raise ValueError("At least one When2Heat component is required")
    unsigned: list[str] = []
    for component in components:
        status = str(component.provenance.get("annual_scaling_status", "")).strip().lower()
        approval_id = str(component.provenance.get("annual_scaling_approval_id", "")).strip()
        if status != "signed" or not approval_id:
            unsigned.append(component.heat_column)
    if unsigned:
        raise ValueError(
            "Executable HP loads require signed annual scaling provenance for "
            f"all components; unsigned={tuple(unsigned)}"
        )


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


def _downscale_component_series(component: HeatPumpComponentSeries) -> HeatPumpComponentSeries:
    return HeatPumpComponentSeries(
        heat_column=component.heat_column,
        cop_column=component.cop_column,
        annual_heat_demand_twh=component.annual_heat_demand_twh,
        end_use=component.end_use,
        building_class=component.building_class,
        thermal_demand_kw=np.repeat(component.thermal_demand_kw, QUARTER_HOURS_PER_HOUR),
        electric_kw=np.repeat(component.electric_kw, QUARTER_HOURS_PER_HOUR),
        cop=np.repeat(component.cop, QUARTER_HOURS_PER_HOUR),
        interval_hours=QUARTER_HOUR_STEP_MINUTES / 60,
        provenance=component.provenance,
    )


def _validate_component_series(
    components: Sequence[HeatPumpComponentSeries],
    *,
    expected_shape: tuple[int, ...],
) -> None:
    for component in components:
        if component.electric_kw.shape != expected_shape:
            raise ValueError("component series must align with aggregate heat-pump demand")


def _weather_content_hash(weather: object) -> str | None:
    value = getattr(weather, "content_sha256", None)
    if value is None:
        identity_record = getattr(weather, "identity_record", None)
        if callable(identity_record):
            record = identity_record()
            if isinstance(record, Mapping):
                value = record.get("content_sha256")
    return _optional_text(value, "weather_content_sha256")


def _optional_text(value: object, label: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        raise ValueError(f"{label} must be non-empty when provided")
    return text


def _required_text_attr(obj: object, name: str) -> str:
    try:
        value = getattr(obj, name)
    except AttributeError as exc:
        raise ValueError(f"weather member must provide {name}") from exc
    if value is None:
        raise ValueError(f"weather {name} must be non-empty")
    text = str(value).strip()
    if not text:
        raise ValueError(f"weather {name} must be non-empty")
    return text


def _weather_provenance(weather: object) -> dict[str, Any]:
    provenance: dict[str, Any] = {}
    for attribute in ("metadata", "provenance"):
        raw = getattr(weather, attribute, None)
        if raw is None:
            continue
        provenance.update(_as_provenance_mapping(raw, f"weather {attribute}"))
    return dict(sorted(provenance.items()))


def _when2heat_use_columns(
    components: Sequence[When2HeatComponent],
    *,
    timestamp_column: str,
    local_timestamp_column: str | None,
) -> set[str]:
    columns = {timestamp_column}
    if local_timestamp_column is not None:
        columns.add(local_timestamp_column)
    for component in components:
        columns.add(component.heat_column)
        columns.add(component.cop_column)
    return columns


def _require_exact_hp001_classes(values: Mapping[str, float], *, label: str) -> None:
    keys = tuple(values)
    required = set(HP001_RESIDENTIAL_BUILDING_CLASSES)
    provided = set(keys)
    if provided != required:
        missing = tuple(sorted(required - provided))
        extra = tuple(sorted(provided - required))
        raise ValueError(
            f"{label} must contain exactly HP-001 residential classes "
            f"{HP001_RESIDENTIAL_BUILDING_CLASSES}; missing={missing}, extra={extra}"
        )


def _paired_pv_weather_field_names(weather: object, *, expected_shape: tuple[int, ...]) -> tuple[str, ...]:
    names: list[str] = []
    fields = getattr(weather, "pv_weather_fields", None)
    if fields is not None:
        if not isinstance(fields, Mapping):
            raise ValueError("weather pv_weather_fields must be a mapping")
        for name, values in fields.items():
            text = str(name).strip()
            if not text:
                raise ValueError("weather pv_weather_fields names must be non-empty")
            _validate_aligned_weather_field(values, text, expected_shape=expected_shape)
            names.append(text)
    for name in PV_WEATHER_FIELD_CANDIDATES:
        if not hasattr(weather, name):
            continue
        values = getattr(weather, name)
        if values is None:
            continue
        _validate_aligned_weather_field(values, name, expected_shape=expected_shape)
        names.append(name)
    if not names:
        raise ValueError("weather member must provide at least one aligned PV/irradiance weather field")
    return tuple(sorted(set(names)))


def _validate_aligned_weather_field(values: object, name: str, *, expected_shape: tuple[int, ...]) -> None:
    array = np.asarray(values, dtype=np.float64)
    if array.shape != expected_shape:
        raise ValueError(f"weather {name} must align with heat-pump demand")
    if not np.isfinite(array).all():
        raise ValueError(f"weather {name} must contain only finite values")


def _coerce_field_names(names: Sequence[str], label: str) -> tuple[str, ...]:
    cleaned = tuple(str(name).strip() for name in names)
    if not cleaned or any(not name for name in cleaned):
        raise ValueError(f"{label} must contain at least one non-empty field name")
    return tuple(sorted(set(cleaned)))


def _as_provenance_mapping(raw: Mapping[str, Any], label: str) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return dict(sorted((str(key), value) for key, value in raw.items()))


def _coerce_optional_local_timestamps(
    timestamps_local: Sequence[datetime] | None,
    timestamps_utc: Sequence[datetime],
) -> tuple[datetime, ...] | None:
    if timestamps_local is None:
        return None
    local = tuple(_as_aware_timestamp(item, "timestamps_local") for item in timestamps_local)
    if len(local) != len(timestamps_utc):
        raise ValueError("UTC and local timestamp counts must match")
    for utc_timestamp, local_timestamp in zip(timestamps_utc, local, strict=True):
        if local_timestamp.astimezone(UTC) != utc_timestamp:
            raise ValueError("UTC and local timestamps must represent the same instants")
    return local


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
    return _as_aware_timestamp(value, "timestamps").astimezone(UTC)


def _as_aware_timestamp(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{label} entries must be datetimes")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value
