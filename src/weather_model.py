from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import hashlib
import json
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

LOCAL_TIMEZONE = "Europe/Amsterdam"
STEP_SECONDS_15MIN = 900
DEFAULT_GHI_FIELD = "ghi_w_per_m2"


@dataclass(frozen=True)
class WeatherMember:
    """Paired HP/PV weather realization on one auditable calendar.

    The member is the ALEA-001 common weather driver: temperature and PV
    weather fields are carried together so HP and PV cannot silently consume
    separate weather realizations.
    """

    member_id: str
    shared_weather_driver_id: str
    source: str
    timestamps_utc: Sequence[datetime]
    timestamps_local: Sequence[datetime]
    temperature_c: Sequence[float]
    pv_weather_fields: Mapping[str, Sequence[float]]
    provenance: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        member_id = _required_text(self.member_id, "member_id")
        driver_id = _required_text(self.shared_weather_driver_id, "shared_weather_driver_id")
        source = _required_text(self.source, "source")
        timestamps_utc = tuple(_as_aware_datetime(item, "timestamps_utc").astimezone(UTC) for item in self.timestamps_utc)
        timestamps_local = tuple(_as_aware_datetime(item, "timestamps_local") for item in self.timestamps_local)
        if len(timestamps_utc) < 2:
            raise ValueError("Weather member must contain at least two timestamps")
        if len(timestamps_utc) != len(timestamps_local):
            raise ValueError("UTC and local timestamp counts must match")
        _validate_strictly_chronological(timestamps_utc)
        _validate_one_cadence(timestamps_utc)
        for utc_timestamp, local_timestamp in zip(timestamps_utc, timestamps_local, strict=True):
            if local_timestamp.astimezone(UTC) != utc_timestamp:
                raise ValueError("UTC and local timestamps must represent the same instants")

        temperature = _as_float_vector(self.temperature_c, "temperature_c")
        if len(temperature) != len(timestamps_utc):
            raise ValueError("temperature_c must match the timestamp count")
        pv_fields = _coerce_pv_weather_fields(self.pv_weather_fields, expected_len=len(timestamps_utc))
        provenance = _audit_mapping(self.provenance, "provenance")
        metadata = _audit_mapping(self.metadata, "metadata")

        object.__setattr__(self, "member_id", member_id)
        object.__setattr__(self, "shared_weather_driver_id", driver_id)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "timestamps_utc", timestamps_utc)
        object.__setattr__(self, "timestamps_local", timestamps_local)
        object.__setattr__(self, "temperature_c", temperature)
        object.__setattr__(self, "pv_weather_fields", pv_fields)
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "metadata", metadata)

    @property
    def n_timesteps(self) -> int:
        return len(self.timestamps_utc)

    @property
    def cadence_seconds(self) -> int:
        return _constant_cadence_seconds(self.timestamps_utc)

    @property
    def ghi_w_per_m2(self) -> np.ndarray:
        """Global horizontal irradiance channel used by the PV scaffold."""
        try:
            return self.pv_weather_fields[DEFAULT_GHI_FIELD]
        except KeyError as exc:
            raise AttributeError(DEFAULT_GHI_FIELD) from exc

    @property
    def content_sha256(self) -> str:
        """Stable content/provenance hash for HP/PV identity comparison."""
        payload = {
            "member_id": self.member_id,
            "shared_weather_driver_id": self.shared_weather_driver_id,
            "source": self.source,
            "timestamps_utc": [item.isoformat() for item in self.timestamps_utc],
            "timestamps_local": [item.isoformat() for item in self.timestamps_local],
            "temperature_c": _array_digest(self.temperature_c),
            "pv_weather_fields": {
                name: _array_digest(values)
                for name, values in sorted(self.pv_weather_fields.items())
            },
            "provenance": self.provenance,
            "metadata": self.metadata,
        }
        return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()

    def identity_record(self) -> dict[str, object]:
        """Return the audit record HP and PV outputs can copy into manifests."""
        return {
            "member_id": self.member_id,
            "shared_weather_driver_id": self.shared_weather_driver_id,
            "source": self.source,
            "first_timestamp_utc": self.timestamps_utc[0].isoformat(),
            "last_timestamp_utc": self.timestamps_utc[-1].isoformat(),
            "first_timestamp_local": self.timestamps_local[0].isoformat(),
            "last_timestamp_local": self.timestamps_local[-1].isoformat(),
            "n_timesteps": self.n_timesteps,
            "cadence_seconds": self.cadence_seconds,
            "temperature_field": "temperature_c",
            "pv_weather_field_names": tuple(sorted(self.pv_weather_fields)),
            "content_sha256": self.content_sha256,
            "provenance": dict(self.provenance),
            "metadata": dict(self.metadata),
        }


def canonical_15min_utc_axis_for_local_year(
    year: int,
    *,
    timezone: str = LOCAL_TIMEZONE,
) -> tuple[datetime, ...]:
    """Return the UTC 15-minute axis for one complete local calendar year."""
    local_zone = ZoneInfo(timezone)
    start_utc = datetime(int(year), 1, 1, tzinfo=local_zone).astimezone(UTC)
    end_utc = datetime(int(year) + 1, 1, 1, tzinfo=local_zone).astimezone(UTC)
    step = timedelta(seconds=STEP_SECONDS_15MIN)
    values: list[datetime] = []
    current = start_utc
    while current < end_utc:
        values.append(current)
        current += step
    if current != end_utc:
        raise AssertionError("15-minute axis did not land on local year boundary")
    return tuple(values)


def canonical_15min_local_axis_for_year(
    year: int,
    *,
    timezone: str = LOCAL_TIMEZONE,
) -> tuple[datetime, ...]:
    """Return local timestamps paired to the canonical UTC axis."""
    local_zone = ZoneInfo(timezone)
    return tuple(
        item.astimezone(local_zone)
        for item in canonical_15min_utc_axis_for_local_year(year, timezone=timezone)
    )


def validate_canonical_15min_calendar(
    member: WeatherMember,
    *,
    local_year: int,
    timezone: str = LOCAL_TIMEZONE,
) -> None:
    """Validate that a member covers one complete 15-minute local year."""
    expected_utc = canonical_15min_utc_axis_for_local_year(local_year, timezone=timezone)
    expected_local = canonical_15min_local_axis_for_year(local_year, timezone=timezone)
    if member.timestamps_utc != expected_utc:
        raise ValueError(f"Weather member does not match the canonical {local_year} UTC calendar")
    if member.timestamps_local != expected_local:
        raise ValueError(f"Weather member does not match the canonical {local_year} local calendar")


def assert_same_weather_realization(
    left: Mapping[str, object] | WeatherMember,
    right: Mapping[str, object] | WeatherMember,
) -> None:
    """Raise unless two records prove the same shared weather realization."""
    left_record = left.identity_record() if isinstance(left, WeatherMember) else dict(left)
    right_record = right.identity_record() if isinstance(right, WeatherMember) else dict(right)
    for key in (
        "member_id",
        "shared_weather_driver_id",
        "source",
        "first_timestamp_utc",
        "last_timestamp_utc",
        "n_timesteps",
        "cadence_seconds",
        "content_sha256",
    ):
        if left_record.get(key) != right_record.get(key):
            raise ValueError(f"weather realization mismatch on {key}")


def _required_text(value: str, name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


def _as_aware_datetime(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{name} entries must be datetimes")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} entries must be timezone-aware")
    return value


def _validate_strictly_chronological(values: Sequence[datetime]) -> None:
    for previous, current in zip(values, values[1:]):
        if current <= previous:
            raise ValueError("Weather member timestamps must be complete and chronological")


def _validate_one_cadence(values: Sequence[datetime]) -> None:
    _constant_cadence_seconds(values)


def _constant_cadence_seconds(values: Sequence[datetime]) -> int:
    deltas = {int((current - previous).total_seconds()) for previous, current in zip(values, values[1:])}
    if len(deltas) != 1:
        raise ValueError("Weather member timestamps must have one constant cadence")
    cadence = deltas.pop()
    if cadence <= 0:
        raise ValueError("Weather member timestamp cadence must be positive")
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


def _coerce_pv_weather_fields(
    raw_fields: Mapping[str, Sequence[float]],
    *,
    expected_len: int,
) -> dict[str, np.ndarray]:
    if not isinstance(raw_fields, Mapping):
        raise ValueError("pv_weather_fields must be a mapping")
    fields: dict[str, np.ndarray] = {}
    for raw_name, raw_values in raw_fields.items():
        name = str(raw_name).strip()
        if not name:
            raise ValueError("pv_weather_fields names must be non-empty")
        values = _as_float_vector(raw_values, name)
        if len(values) != expected_len:
            raise ValueError(f"{name} must match the timestamp count")
        if (values < 0).any():
            raise ValueError(f"{name} must be non-negative")
        fields[name] = values
    if not fields:
        raise ValueError("pv_weather_fields must include at least one irradiance/PV weather field")
    if DEFAULT_GHI_FIELD not in fields:
        raise ValueError(f"pv_weather_fields must include {DEFAULT_GHI_FIELD}")
    return dict(sorted(fields.items()))


def _audit_mapping(raw: Mapping[str, Any], label: str) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"{label} must be a mapping")
    copied = dict(sorted((str(key), value) for key, value in raw.items()))
    _canonical_json_bytes(copied)
    return copied


def _array_digest(array: np.ndarray) -> dict[str, object]:
    contiguous = np.ascontiguousarray(array, dtype=np.float64)
    return {
        "dtype": "float64",
        "shape": list(contiguous.shape),
        "sha256": hashlib.sha256(contiguous.tobytes()).hexdigest(),
    }


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except TypeError as exc:
        raise ValueError("weather provenance and metadata must be JSON-serializable") from exc
