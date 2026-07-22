from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np

from src.contracts.net_load import ExecutableInputArtifact
from src.weather_model import (
    LOCAL_TIMEZONE,
    STEP_SECONDS_15MIN,
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
    weather_identity: Mapping[str, object] = field(default_factory=dict)

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
        weather_identity = _audit_json_mapping(self.weather_identity, "weather_identity")
        if weather_identity:
            if weather_identity.get("member_id") != self.weather_member_id:
                raise ValueError("weather_identity member_id must match weather_member_id")
            if weather_identity.get("shared_weather_driver_id") != self.shared_weather_driver_id:
                raise ValueError("weather_identity shared_weather_driver_id must match shared_weather_driver_id")

        object.__setattr__(self, "timestamps_utc", timestamps_utc)
        object.__setattr__(self, "timestamps_local", timestamps_local)
        object.__setattr__(self, "generation_kw", generation)
        object.__setattr__(self, "weather_identity", weather_identity)

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

    @property
    def weather_content_sha256(self) -> str | None:
        value = self.weather_identity.get("content_sha256")
        return None if value is None else str(value)

    def identity_record(self) -> dict[str, object]:
        """Return PV output identity fields for later HP/PV pairing checks."""
        record = {
            "member_id": self.weather_member_id,
            "weather_member_id": self.weather_member_id,
            "source": self.weather_source,
            "weather_source": self.weather_source,
            "shared_weather_driver_id": self.shared_weather_driver_id,
            "content_sha256": self.weather_content_sha256,
            "weather_content_sha256": self.weather_content_sha256,
            "first_timestamp_utc": self.timestamps_utc[0].isoformat(),
            "last_timestamp_utc": self.timestamps_utc[-1].isoformat(),
            "n_timesteps": self.n_timesteps,
            "cadence_seconds": self.cadence_seconds,
            "config_id": self.config.config_id,
        }
        for key in (
            "source_member_acceptance_id",
            "weather_input_artifact_status",
            "calendar_id",
            "pvgis_realized_weather_path",
            "pvgis_role",
        ):
            if key in self.weather_identity:
                record[key] = self.weather_identity[key]
        return record


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


@dataclass(frozen=True)
class PVWeatherInputArtifact:
    """Accepted WEATHER-001 member index for PV executable-input gating."""

    data_id: str
    selection_id: str
    status: str
    source_member_acceptance_id: str
    weather_contract: str
    accepted_for_source_member_use: bool
    ready_for_executable_input_gate: bool
    realized_weather_path: str
    pvgis_role: str
    pvgis_realized_weather_path: bool
    required_identity_fields_for_hp_pv_pairing: Sequence[str]
    calendar_contract: Mapping[str, object]
    members: Sequence[Mapping[str, object]]
    blocked_acceptance_gates: Mapping[str, object]
    evidence_artifacts: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.data_id != "D-004":
            raise ValueError("PV weather input artifact must identify D-004")
        if not self.selection_id:
            raise ValueError("selection_id must be non-empty")
        if not self.source_member_acceptance_id:
            raise ValueError("source_member_acceptance_id must be non-empty")
        if self.weather_contract != "WEATHER-001":
            raise ValueError("PV weather input artifact must use WEATHER-001")
        if self.accepted_for_source_member_use is not True:
            raise ValueError("PV weather input artifact must be accepted for source/member use")
        if self.ready_for_executable_input_gate is not True:
            raise ValueError("PV weather input artifact must be ready for executable-input gating")
        if self.pvgis_realized_weather_path is not False:
            raise ValueError("PVGIS must remain outside the realized weather path")
        required_fields = tuple(str(item) for item in self.required_identity_fields_for_hp_pv_pairing)
        required = {
            "member_id",
            "shared_weather_driver_id",
            "source",
            "first_timestamp_utc",
            "last_timestamp_utc",
            "n_timesteps",
            "cadence_seconds",
            "content_sha256",
        }
        if not required.issubset(required_fields):
            raise ValueError("PV weather input artifact lacks required HP/PV identity fields")
        members = tuple(_audit_json_mapping(item, "weather_input_artifact member") for item in self.members)
        if not members:
            raise ValueError("PV weather input artifact must include at least one member")
        calendar_contract = _audit_json_mapping(self.calendar_contract, "calendar_contract")
        blocked_gates = _audit_json_mapping(self.blocked_acceptance_gates, "blocked_acceptance_gates")
        for gate in ("final_paired_hp_pv_acceptance", "cold_spell_acceptance", "integrated_analysis"):
            gate_record = blocked_gates.get(gate)
            if not isinstance(gate_record, Mapping) or gate_record.get("blocked") is not True:
                raise ValueError(f"PV weather input artifact must keep {gate} blocked")
        for member in members:
            _validate_weather_input_member_record(member, acceptance_id=self.source_member_acceptance_id)
            if int(member["cadence_seconds"]) != int(calendar_contract.get("cadence_seconds", 0)):
                raise ValueError("member cadence_seconds must match the artifact calendar contract")

        object.__setattr__(self, "required_identity_fields_for_hp_pv_pairing", required_fields)
        evidence_artifacts = _audit_json_mapping(self.evidence_artifacts, "evidence_artifacts")
        object.__setattr__(self, "calendar_contract", calendar_contract)
        object.__setattr__(self, "members", members)
        object.__setattr__(self, "blocked_acceptance_gates", blocked_gates)
        object.__setattr__(self, "evidence_artifacts", evidence_artifacts)

    def member_for_year(self, year: int) -> Mapping[str, object]:
        """Return the accepted member record for a UTC calendar year."""
        for member in self.members:
            if int(member["year"]) == int(year):
                return member
        raise KeyError(f"no D-004 weather input member for year {year}")

    def member_for_id(self, member_id: str) -> Mapping[str, object]:
        """Return the accepted member record for a WEATHER-001 member ID."""
        for member in self.members:
            if member["member_id"] == member_id:
                return member
        raise KeyError(f"no D-004 weather input member for member_id {member_id!r}")


def load_pv_weather_input_artifact(path: str | Path) -> PVWeatherInputArtifact:
    """Load an accepted WEATHER-001 member index for PV input readiness."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return PVWeatherInputArtifact(
        data_id=str(payload.get("data_id", "")),
        selection_id=str(payload.get("selection_id", "")),
        status=str(payload.get("status", "")),
        source_member_acceptance_id=str(payload.get("source_member_acceptance_id", "")),
        weather_contract=str(payload.get("weather_contract", "")),
        accepted_for_source_member_use=payload.get("accepted_for_source_member_use"),
        ready_for_executable_input_gate=payload.get("ready_for_executable_input_gate"),
        realized_weather_path=str(payload.get("realized_weather_path", "")),
        pvgis_role=str(payload.get("pvgis_role", "")),
        pvgis_realized_weather_path=payload.get("pvgis_realized_weather_path"),
        required_identity_fields_for_hp_pv_pairing=payload.get("required_identity_fields_for_hp_pv_pairing", ()),
        calendar_contract=payload.get("calendar_contract", {}),
        members=payload.get("members", ()),
        blocked_acceptance_gates=payload.get("blocked_acceptance_gates", {}),
        evidence_artifacts=payload.get("evidence_artifacts", {}),
    )


def build_pv_ic1_executable_input_artifact(
    artifact: PVWeatherInputArtifact,
    *,
    year: int,
    node_ids: Sequence[str],
    manifest_path: str | None = None,
    artifact_id: str | None = None,
    source_id: str | None = None,
    version_id: str | None = None,
    ic1_calendar_id: str | None = None,
) -> ExecutableInputArtifact:
    """Convert accepted D-004 PV/weather metadata into an IC-1 gate artifact.

    The returned object is metadata-only: it does not load PV trajectories,
    map historical weather onto a planning calendar, assemble net load, or
    relax the later paired HP/PV and cold-spell acceptance gates.
    """
    member = artifact.member_for_year(year)
    source_calendar_id = str(member["calendar_id"])
    target_calendar_id = source_calendar_id if ic1_calendar_id is None else str(ic1_calendar_id)
    evidence_path = _default_weather_input_artifact_path(artifact)
    manifest = evidence_path if manifest_path is None else manifest_path
    deferred_gates = tuple(
        gate
        for gate, value in sorted(artifact.blocked_acceptance_gates.items())
        if isinstance(value, Mapping) and value.get("blocked") is True
    )
    provenance = {
        "weather_contract": artifact.weather_contract,
        "source_member_acceptance_id": artifact.source_member_acceptance_id,
        "weather_input_artifact_status": artifact.status,
        "selection_id": artifact.selection_id,
        "source_calendar_id": source_calendar_id,
        "source_cadence_seconds": int(member["cadence_seconds"]),
        "source_n_timesteps": int(member["n_timesteps"]),
        "source_first_timestamp_utc": str(member["first_timestamp_utc"]),
        "source_last_timestamp_utc": str(member["last_timestamp_utc"]),
        "content_sha256": str(member["content_sha256"]),
        "shared_weather_driver_id": str(member["shared_weather_driver_id"]),
        "realized_weather_path": artifact.realized_weather_path,
        "pvgis_role": artifact.pvgis_role,
        "pvgis_realized_weather_path": artifact.pvgis_realized_weather_path,
        "deferred_acceptance_gates": deferred_gates,
        "no_net_load_or_event_analysis": True,
    }
    if target_calendar_id != source_calendar_id:
        provenance["ic1_calendar_id"] = target_calendar_id
        provenance["calendar_mapping_status"] = "caller_supplied_not_d004_signed_by_this_helper"
    # D004-SOURCE-MEMBER-ACCEPTANCE is source/member acceptance only; the
    # deferred gate list stays manifest-visible so IC-1 cannot launder this
    # artifact into final paired/cold-spell acceptance.
    return ExecutableInputArtifact(
        artifact_id=artifact_id or f"{artifact.selection_id}:pv_weather:{year}",
        kind="pv",
        artifact_status="accepted",
        version_id=version_id or artifact.selection_id,
        source_id=source_id or f"D-004:{artifact.selection_id}:WEATHER-001:pv",
        member_id=str(member["member_id"]),
        calendar_id=target_calendar_id,
        node_ids=tuple(node_ids),
        signed_register_ids=("WEATHER-001", "D004-MC-001", "D004-SOURCE-MEMBER-ACCEPTANCE"),
        timestep_seconds=int(member["cadence_seconds"]),
        shared_weather_driver_id=str(member["shared_weather_driver_id"]),
        manifest_path=manifest,
        provenance=provenance,
    )

def assert_weather_member_matches_input_artifact(
    weather: WeatherMember | Mapping[str, object],
    artifact: PVWeatherInputArtifact,
    *,
    year: int | None = None,
    member_id: str | None = None,
) -> Mapping[str, object]:
    """Raise unless a WEATHER-001 record is one accepted D-004 input member."""
    identity = weather.identity_record() if isinstance(weather, WeatherMember) else dict(weather)
    if year is not None:
        member = artifact.member_for_year(year)
    else:
        lookup_id = member_id or str(identity.get("member_id", ""))
        member = artifact.member_for_id(lookup_id)
    for key in artifact.required_identity_fields_for_hp_pv_pairing:
        if identity.get(key) != member.get(key):
            raise ValueError(f"weather input artifact mismatch on {key}")
    for key in ("first_timestamp_local", "last_timestamp_local"):
        if key in identity and identity.get(key) != member.get(key):
            raise ValueError(f"weather input artifact mismatch on {key}")
    return member


def generate_pv_profile_from_input_artifact(
    weather: WeatherMember,
    config: PVSystemConfig,
    artifact: PVWeatherInputArtifact,
    *,
    year: int | None = None,
) -> PVGenerationProfile:
    """Generate PV only after the weather member matches the accepted artifact."""
    member = assert_weather_member_matches_input_artifact(weather, artifact, year=year)
    profile = generate_pv_profile(weather, config)
    identity = dict(profile.weather_identity)
    identity.update(
        {
            "source_member_acceptance_id": artifact.source_member_acceptance_id,
            "weather_input_artifact_status": artifact.status,
            "calendar_id": member["calendar_id"],
            "pvgis_realized_weather_path": artifact.pvgis_realized_weather_path,
            "pvgis_role": artifact.pvgis_role,
        }
    )
    return PVGenerationProfile(
        weather_member_id=profile.weather_member_id,
        weather_source=profile.weather_source,
        shared_weather_driver_id=profile.shared_weather_driver_id,
        timestamps_utc=profile.timestamps_utc,
        timestamps_local=profile.timestamps_local,
        generation_kw=profile.generation_kw,
        config=config,
        weather_identity=identity,
    )


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
        weather_identity=weather.identity_record(),
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
        "weather_content_sha256": profile.weather_content_sha256,
        "weather_identity_record": profile.identity_record(),
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


def _default_weather_input_artifact_path(artifact: PVWeatherInputArtifact) -> str:
    raw_path = artifact.evidence_artifacts.get("weather_input_artifact")
    if isinstance(raw_path, str) and raw_path:
        return raw_path
    return f"data/metadata/weather_pv/{artifact.selection_id}_weather_input_artifact.json"

def _validate_weather_input_member_record(member: Mapping[str, object], *, acceptance_id: str) -> None:
    required = (
        "year",
        "member_id",
        "shared_weather_driver_id",
        "source",
        "content_sha256",
        "calendar_id",
        "cadence_seconds",
        "n_timesteps",
        "first_timestamp_utc",
        "last_timestamp_utc",
        "source_member_acceptance_id",
        "accepted_for_source_member_use",
        "final_paired_hp_pv_acceptance",
        "cold_spell_acceptance",
    )
    missing = [key for key in required if key not in member]
    if missing:
        raise ValueError(f"weather input artifact member missing fields: {missing}")
    if member["source_member_acceptance_id"] != acceptance_id:
        raise ValueError("member source_member_acceptance_id must match the artifact")
    if member["accepted_for_source_member_use"] is not True:
        raise ValueError("member must be accepted for source/member use")
    if member["final_paired_hp_pv_acceptance"] is not False:
        raise ValueError("member must not imply final paired HP/PV acceptance")
    if member["cold_spell_acceptance"] is not False:
        raise ValueError("member must not imply cold-spell acceptance")
    if len(str(member["content_sha256"])) != 64:
        raise ValueError("member content_sha256 must be a SHA-256 hex digest")
    if int(member["cadence_seconds"]) != STEP_SECONDS_15MIN:
        raise ValueError("member cadence_seconds must be 900")
    if int(member["n_timesteps"]) <= 0:
        raise ValueError("member n_timesteps must be positive")


def _audit_json_mapping(raw: Mapping[str, object], label: str) -> Mapping[str, object]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"{label} must be a mapping")
    copied = dict(sorted((str(key), value) for key, value in raw.items()))
    try:
        json.dumps(copied, sort_keys=True, separators=(",", ":"))
    except TypeError as exc:
        raise ValueError(f"{label} must be JSON-serializable") from exc
    return MappingProxyType(copied)


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
