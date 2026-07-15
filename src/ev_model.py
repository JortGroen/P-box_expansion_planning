from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import gzip
import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np


EXPECTED_FULL_YEAR_STEPS = 35_040
STEP_HOURS = 0.25
LOCAL_TIMEZONE = "Europe/Amsterdam"


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

    def sample_member_indices(self, n_members: int, *, seed: int, replace: bool = False) -> np.ndarray:
        if n_members < 0:
            raise ValueError("n_members must be non-negative")
        if not replace and n_members > self.batch.n_profiles:
            raise ValueError("Cannot sample more distinct members than are available")
        rng = np.random.default_rng(seed)
        return rng.choice(self.batch.n_profiles, size=n_members, replace=replace)

    def sample_profiles_kw(self, n_members: int, *, seed: int, replace: bool = False) -> np.ndarray:
        indices = self.sample_member_indices(n_members, seed=seed, replace=replace)
        return self.batch.demands_kw[:, indices]

    def sample_aggregate_kw(self, n_members: int, *, seed: int, replace: bool = False) -> np.ndarray:
        profiles = self.sample_profiles_kw(n_members, seed=seed, replace=replace)
        return profiles.sum(axis=1)


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
