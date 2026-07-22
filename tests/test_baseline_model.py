from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from src.baseline_model import (
    BASELINE_COMPONENT,
    BaselineLoadTrajectory,
    BaselineTrajectoryLibrary,
    component_calendar_footprint,
    validate_canonical_calendar,
    validate_component_calendar_readiness,
)
from src.weather_model import (
    canonical_15min_local_axis_for_year,
    canonical_15min_utc_axis_for_local_year,
)


def _calendar(n_steps: int = 96) -> tuple[datetime, ...]:
    start = datetime(2025, 1, 3, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
    return tuple(start + timedelta(minutes=15 * index) for index in range(n_steps))


def _trajectory(
    *,
    trajectory_id: str = "baseline_a",
    timestamps: tuple[datetime, ...] | None = None,
) -> BaselineLoadTrajectory:
    axis = timestamps or _calendar()
    values = np.column_stack(
        [
            np.arange(len(axis), dtype=np.float64),
            np.arange(len(axis), dtype=np.float64) + 100.0,
        ]
    )
    return BaselineLoadTrajectory(
        timestamps=axis,
        load_kw=values,
        trajectory_id=trajectory_id,
        source_id="synthetic_baseline_fixture",
    )


def test_baseline_trajectory_records_alea_metadata_without_congestion_claims() -> None:
    trajectory = _trajectory()
    metadata = trajectory.metadata().manifest_record()

    assert metadata["component"] == BASELINE_COMPONENT
    assert metadata["trajectory_id"] == "baseline_a"
    assert metadata["calendar_timezone"] == "Europe/Amsterdam"
    assert metadata["n_timesteps"] == 96
    assert metadata["n_series"] == 2
    assert metadata["preserves_temporal_order"] is True
    assert metadata["weekday_weekend_preserved"] is True
    assert metadata["seasonal_order_preserved"] is True
    assert metadata["congestion_evaluated"] is False
    assert metadata["adequacy_certified"] is False
    assert len(str(metadata["time_axis_sha256"])) == 64
    assert len(str(metadata["values_sha256"])) == 64


def test_complete_trajectory_values_and_calendar_order_are_preserved() -> None:
    trajectory = _trajectory()
    values = trajectory.values()

    assert np.array_equal(values[:, 0], np.arange(96, dtype=np.float64))
    assert trajectory.weekday_weekend_labels()[:4] == ("weekday", "weekday", "weekday", "weekday")
    assert set(trajectory.season_labels()) == {"winter"}
    values[0, 0] = -999.0
    assert trajectory.values()[0, 0] == 0.0


def test_library_selection_is_deterministic_and_manifestable() -> None:
    first = _trajectory(trajectory_id="baseline_a")
    second = _trajectory(trajectory_id="baseline_b")
    library = BaselineTrajectoryLibrary((first, second))

    assert library.n_trajectories == 2
    assert library.trajectory(0).trajectory_id == "baseline_a"
    assert library.trajectory(0).trajectory_id == "baseline_a"
    assert [record["trajectory_id"] for record in library.metadata_records()] == [
        "baseline_a",
        "baseline_b",
    ]


def test_calendar_validation_rejects_mismatched_timestamps() -> None:
    trajectory = _trajectory()
    mismatched = tuple(item + timedelta(minutes=15) for item in _calendar())

    with pytest.raises(ValueError, match="canonical calendar"):
        trajectory.require_calendar(mismatched)

    with pytest.raises(ValueError, match="canonical calendar"):
        BaselineTrajectoryLibrary((trajectory, _trajectory(timestamps=mismatched)))


def test_calendar_validation_rejects_naive_and_non_15_minute_axes() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        validate_canonical_calendar((datetime(2025, 1, 1, 0, 0),))

    bad_spacing = (
        datetime(2025, 1, 1, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam")),
        datetime(2025, 1, 1, 0, 10, tzinfo=ZoneInfo("Europe/Amsterdam")),
    )
    with pytest.raises(ValueError, match="15-minute"):
        validate_canonical_calendar(bad_spacing)


def test_load_validation_reports_clear_errors() -> None:
    axis = _calendar(4)

    with pytest.raises(ValueError, match="length"):
        BaselineLoadTrajectory(
            timestamps=axis,
            load_kw=np.ones(3),
            trajectory_id="short",
            source_id="fixture",
        )

    values = np.ones(4)
    values[2] = np.nan
    with pytest.raises(ValueError, match="finite"):
        BaselineLoadTrajectory(
            timestamps=axis,
            load_kw=values,
            trajectory_id="nan",
            source_id="fixture",
        )


def test_component_calendar_readiness_aligns_baseline_ev_hp_and_pv_on_canonical_year() -> None:
    utc_axis = canonical_15min_utc_axis_for_local_year(2035)
    local_axis = canonical_15min_local_axis_for_year(2035)
    records = (
        component_calendar_footprint(
            component="baseline",
            timestamps=local_axis,
            member_id="simbench-baseline-s0",
            source_id="D-001",
        ),
        component_calendar_footprint(
            component="ev",
            timestamps=utc_axis,
            member_id="ev-candidate-profile_140001_000",
            source_id="D-002",
        ),
        component_calendar_footprint(
            component="hp",
            timestamps=utc_axis,
            member_id="hp-weather-member-1997",
            source_id="D-003",
            shared_weather_driver_id="weather:knmi-1997",
        ),
        component_calendar_footprint(
            component="pv",
            timestamps=local_axis,
            member_id="pv-weather-member-1997",
            source_id="D-004",
            shared_weather_driver_id="weather:knmi-1997",
        ),
    )

    readiness = validate_component_calendar_readiness(records, local_year=2035)
    manifest = readiness.manifest_record()

    assert manifest["calendar_id"] == "e2_s5_common_15min_2035_Europe/Amsterdam"
    assert manifest["n_timesteps"] == 35_040
    assert manifest["cadence_seconds"] == 900
    assert manifest["shared_weather_driver_id"] == "weather:knmi-1997"
    assert manifest["aligned_on_common_calendar"] is True
    assert manifest["congestion_evaluated"] is False
    assert manifest["adequacy_certified"] is False
    assert manifest["manuscript_numbers_produced"] is False
    assert {
        record["component"]
        for record in manifest["component_records"]  # type: ignore[index]
    } == {"baseline", "ev", "hp", "pv"}


def test_component_calendar_readiness_rejects_mismatched_component_calendar() -> None:
    utc_axis = canonical_15min_utc_axis_for_local_year(2035)
    shifted = tuple(item + timedelta(minutes=15) for item in utc_axis)
    records = (
        component_calendar_footprint(
            component="baseline",
            timestamps=utc_axis,
            member_id="baseline",
            source_id="D-001",
        ),
        component_calendar_footprint(
            component="ev",
            timestamps=shifted,
            member_id="ev",
            source_id="D-002",
        ),
        component_calendar_footprint(
            component="hp",
            timestamps=utc_axis,
            member_id="hp",
            source_id="D-003",
            shared_weather_driver_id="weather-a",
        ),
        component_calendar_footprint(
            component="pv",
            timestamps=utc_axis,
            member_id="pv",
            source_id="D-004",
            shared_weather_driver_id="weather-a",
        ),
    )

    with pytest.raises(ValueError, match="ev does not match"):
        validate_component_calendar_readiness(records, local_year=2035)


def test_component_calendar_readiness_rejects_unpaired_hp_pv_weather() -> None:
    utc_axis = canonical_15min_utc_axis_for_local_year(2035)
    records = (
        component_calendar_footprint(
            component="baseline",
            timestamps=utc_axis,
            member_id="baseline",
            source_id="D-001",
        ),
        component_calendar_footprint(
            component="ev",
            timestamps=utc_axis,
            member_id="ev",
            source_id="D-002",
        ),
        component_calendar_footprint(
            component="hp",
            timestamps=utc_axis,
            member_id="hp",
            source_id="D-003",
            shared_weather_driver_id="weather-a",
        ),
        component_calendar_footprint(
            component="pv",
            timestamps=utc_axis,
            member_id="pv",
            source_id="D-004",
            shared_weather_driver_id="weather-b",
        ),
    )

    with pytest.raises(ValueError, match="same shared_weather_driver_id"):
        validate_component_calendar_readiness(records, local_year=2035)


def test_component_calendar_readiness_rejects_missing_component_and_duplicate_names() -> None:
    utc_axis = canonical_15min_utc_axis_for_local_year(2035)
    baseline = component_calendar_footprint(
        component="baseline",
        timestamps=utc_axis,
        member_id="baseline-a",
        source_id="D-001",
    )

    with pytest.raises(ValueError, match="Missing required"):
        validate_component_calendar_readiness((baseline,), local_year=2035)

    duplicate = component_calendar_footprint(
        component="baseline",
        timestamps=utc_axis,
        member_id="baseline-b",
        source_id="D-001",
    )
    with pytest.raises(ValueError, match="unique component names"):
        validate_component_calendar_readiness(
            (baseline, duplicate),
            local_year=2035,
            required_components=("baseline",),
        )
