from __future__ import annotations

from datetime import UTC, datetime, timedelta
import gzip
import json
from pathlib import Path

import numpy as np
import pytest

from src.ev_model import (
    EVProfileBootstrapSampler,
    EXPECTED_FULL_YEAR_STEPS,
    distinct_member_count,
    load_processed_batch_npz,
    parse_elaad_profile_response,
    save_processed_batch_npz,
)


def _payload(n_profiles: int = 3, timesteps: int = EXPECTED_FULL_YEAR_STEPS) -> dict:
    start = datetime(2024, 12, 31, 23, 0, tzinfo=UTC)
    datetimes = [(start + timedelta(minutes=15 * index)).isoformat() for index in range(timesteps)]
    demands = [
        [float(profile + 1 + (step % 4)) for profile in range(n_profiles)]
        for step in range(timesteps)
    ]
    return {
        "config": {"seed": 130001, "n_profiles": n_profiles},
        "statistics": None,
        "profile": {
            "cp_ids": [f"profile_{index}" for index in range(n_profiles)],
            "datetimes": datetimes,
            "demands_kw": demands,
        },
    }


def test_parse_time_major_response_and_timezone() -> None:
    batch = parse_elaad_profile_response(_payload(), batch_seed=130001, expected_n_profiles=3)

    assert batch.demands_kw.shape == (EXPECTED_FULL_YEAR_STEPS, 3)
    assert batch.datetimes_utc[0].isoformat() == "2024-12-31T23:00:00+00:00"
    assert batch.datetimes_local[0].isoformat() == "2025-01-01T00:00:00+01:00"
    assert batch.member_ids == ("profile_130001_000", "profile_130001_001", "profile_130001_002")
    assert np.all(batch.annual_energy_kwh() > 0)


def test_parse_rejects_profile_major_output() -> None:
    payload = _payload(n_profiles=2)
    payload["profile"]["demands_kw"] = [[0.0] * EXPECTED_FULL_YEAR_STEPS for _ in range(2)]

    with pytest.raises(ValueError, match="time-major"):
        parse_elaad_profile_response(payload, batch_seed=130001, expected_n_profiles=2)


def test_parse_rejects_nonfinite_values() -> None:
    payload = _payload(n_profiles=1)
    payload["profile"]["demands_kw"][0][0] = None

    with pytest.raises(ValueError, match="missing or non-finite"):
        parse_elaad_profile_response(payload, batch_seed=130001, expected_n_profiles=1)


def test_processed_roundtrip_and_sampler_reproducibility(tmp_path: Path) -> None:
    batch = parse_elaad_profile_response(_payload(n_profiles=4), batch_seed=130001, expected_n_profiles=4)
    path = tmp_path / "batch.npz"
    save_processed_batch_npz(batch, path)
    loaded = load_processed_batch_npz(path)
    sampler = EVProfileBootstrapSampler(loaded)

    # EV-005 leaves replacement unresolved, so tests and production callers
    # must state the provisional sampling rule instead of inheriting a default.
    first = sampler.sample_member_indices(3, seed=42, replace=False)
    second = sampler.sample_member_indices(3, seed=42, replace=False)
    different = sampler.sample_member_indices(3, seed=43, replace=False)

    assert np.array_equal(first, second)
    assert not np.array_equal(first, different)
    assert len(set(first.tolist())) == 3
    assert np.array_equal(
        sampler.sample_aggregate_kw(3, seed=42, replace=False),
        loaded.demands_kw[:, first].sum(axis=1),
    )


def test_sampler_rejects_too_many_without_replacement() -> None:
    batch = parse_elaad_profile_response(_payload(n_profiles=2), batch_seed=130001, expected_n_profiles=2)
    sampler = EVProfileBootstrapSampler(batch)

    with pytest.raises(ValueError, match="more distinct members"):
        sampler.sample_member_indices(3, seed=1, replace=False)


def test_sampler_requires_explicit_replacement_rule() -> None:
    batch = parse_elaad_profile_response(_payload(n_profiles=2), batch_seed=130001, expected_n_profiles=2)
    sampler = EVProfileBootstrapSampler(batch)

    with pytest.raises(TypeError, match="replace"):
        sampler.sample_member_indices(1, seed=1)


def test_distinct_member_count_detects_duplicate_profiles() -> None:
    payload = _payload(n_profiles=2)
    payload["profile"]["demands_kw"] = [[1.0, 1.0] for _ in range(EXPECTED_FULL_YEAR_STEPS)]
    batch = parse_elaad_profile_response(payload, batch_seed=130001, expected_n_profiles=2)

    assert distinct_member_count(batch) == 1


def test_gzip_payload_can_be_parsed(tmp_path: Path) -> None:
    path = tmp_path / "response.json.gz"
    raw = json.dumps(_payload(n_profiles=1)).encode("utf-8")
    with gzip.open(path, "wb") as handle:
        handle.write(raw)

    with gzip.open(path, "rb") as handle:
        batch = parse_elaad_profile_response(handle.read(), batch_seed=130001, expected_n_profiles=1)

    assert batch.n_profiles == 1
